# ---------------------------------------------------------------- shot 4: still preserved (the museum's Egyptian room)
"""4 STILL PRESERVED. The village museum's Egyptian room: sandstone walls cut with rows of hieroglyphs and painted
gods, a gilded sarcophagus, torches of warm light, a stone plinth in a glass case open at the front. The lens high,
looking down on him at the case: he blows the thick dust off a sealed clay honey pot from a tomb, cracks its wax with
his dipper, and lifts out a shining golden ribbon of honey, thousands of years old and perfect; behind him the mummy
sits up in its sarcophagus and reaches for it, and he turns and hands the mummy the dipper."""

S4_P0 = Vector((-0.2, 0.12, 0.0))              # where he stands at the case
S4_YAW = math.radians(24)
S4_FW = Vector((math.sin(S4_YAW), -math.cos(S4_YAW), 0)); S4_OUT = Vector((math.cos(S4_YAW), math.sin(S4_YAW), 0))
S4_POT = S4_P0 + S4_FW * 0.215 + S4_OUT * 0.05     # in front of his dipper hand, a dipper's length away
S4_PL = 0.26                                    # the plinth's top
S4_PK = 0.72                                     # the pot is built at 1/0.72 and scaled down
S4_PH0 = 0.24
S4_PH = S4_PH0 * S4_PK                           # the pot: body and neck
S4_MOUTH = Vector((S4_POT.x, S4_POT.y, S4_PL + S4_PH))
S4_HIP = Vector((S4_P0.x + 0.52, S4_P0.y - 0.04, 0.2))   # the mummy's hip in the sarcophagus (feet to the lens)


def s4_glyph_wall(name, x0, x1, y, z0, z1, rnd):
    """rows of hieroglyphs cut into the sandstone: owls, eyes, reeds, suns, water, men; ochre relief, some painted"""
    relief = K.mat("glyph relief", "#7A4E26", rough=0.85)
    paint = [K.mat(f"glyph paint {c}", c, rough=0.7) for c in ("#2F5C8C", "#A8402A", "#2F7A64", "#C8962E")]
    rows = int((z1 - z0) / 0.085)
    for r in range(rows):
        z = z0 + 0.04 + r * 0.085
        K.box(name + " rule", ((x0 + x1) / 2, y - 0.004, z - 0.042), (x1 - x0, 0.006, 0.006), relief, bev=0)
        x = x0 + 0.03
        while x < x1 - 0.03:
            m = rnd.choice(paint) if rnd.random() < 0.35 else relief
            k = rnd.randrange(6)
            if k == 0:     # a reed
                K.box(name + " reed", (x, y - 0.006, z), (0.008, 0.008, 0.06), m, bev=0.002); w = 0.025
            elif k == 1:   # an eye
                K.sph(name + " eye", (x, y - 0.006, z + 0.005), 1.0, m, scale=(0.022, 0.006, 0.011), seg=12, ring=6)
                K.sph(name + " pupil", (x, y - 0.011, z + 0.005), 0.006, relief, seg=8, ring=6); w = 0.05
            elif k == 2:   # a sun
                K.cyl(name + " sun", (x, y - 0.006, z), 0.016, 0.008, m, rot=(math.pi / 2, 0, 0), v=16, bev=0.002); w = 0.04
            elif k == 3:   # water
                for j in range(3):
                    K.box(name + " water", (x + 0.012 * j - 0.012, y - 0.006, z - 0.012 + 0.004 * (j % 2)), (0.011, 0.007, 0.006), m, bev=0.001)
                w = 0.045
            elif k == 4:   # an owl
                K.sph(name + " owl", (x, y - 0.006, z - 0.005), 1.0, m, scale=(0.012, 0.006, 0.022), seg=12, ring=6)
                K.sph(name + " owl head", (x + 0.006, y - 0.006, z + 0.022), 0.01, m, seg=10, ring=6); w = 0.04
            else:          # a seated man
                K.box(name + " man", (x, y - 0.006, z - 0.015), (0.02, 0.008, 0.02), m, bev=0.003)
                K.box(name + " man body", (x - 0.005, y - 0.006, z + 0.008), (0.01, 0.008, 0.03), m, bev=0.003)
                K.sph(name + " man head", (x - 0.004, y - 0.006, z + 0.03), 0.008, m, seg=8, ring=6); w = 0.04
            x += w + rnd.uniform(0.0, 0.015)


def s4_god(name, x, y, skin, kilt, crown, jackal=False):
    """a painted god on the wall in profile: a tall figure with a kilt, a collar, a staff, and an animal head"""
    sk = K.mat(f"god skin {skin}", skin, rough=0.7); kt = K.mat("god kilt", kilt, rough=0.7)
    cr = K.mat(f"god crown {crown}", crown, rough=0.6); gold = K.mat("god gold", "#D2A23A", rough=0.35, metal=0.6)
    K.box(name + " legs", (x, y, 0.62), (0.07, 0.01, 0.3), sk, bev=0.01)
    K.box(name + " kilt", (x, y - 0.002, 0.78), (0.11, 0.01, 0.14), kt, bev=0.01)
    K.box(name + " body", (x, y, 0.98), (0.1, 0.01, 0.26), sk, bev=0.015)
    K.box(name + " collar", (x, y - 0.004, 1.08), (0.11, 0.01, 0.05), gold, bev=0.01)
    K.sph(name + " head", (x + 0.01, y, 1.18), 1.0, sk if not jackal else cr, scale=(0.05, 0.008, 0.055), seg=16, ring=8)
    if jackal:
        K.box(name + " snout", (x + 0.06, y, 1.17), (0.07, 0.008, 0.03), cr, bev=0.008)
        for dx in (-0.02, 0.015):
            K.box(name + " ear", (x + dx, y, 1.26), (0.018, 0.008, 0.07), cr, bev=0.004)
    else:
        K.box(name + " crown", (x, y - 0.002, 1.27), (0.06, 0.01, 0.1), cr, bev=0.01)
        K.sph(name + " sun disc", (x, y - 0.004, 1.36), 0.04, K.mat("god sun", "#D8402A", rough=0.5), scale=(1, 0.2, 1))
    K.box(name + " staff", (x + 0.09, y - 0.004, 0.85), (0.012, 0.008, 0.66), gold, bev=0.003)
    K.box(name + " arm", (x + 0.05, y - 0.006, 0.98), (0.09, 0.008, 0.025), sk, bev=0.006)


def s4_torch(name, x, y, z, face):
    """a wall torch: an iron bracket, a wrapped head, and a flame with its warm light"""
    iron = K.mat("torch iron", "#3A3430", rough=0.5, metal=0.7)
    K.box(name + " bracket", (x, y + face * 0.04, z - 0.05), (0.03, 0.08, 0.02), iron, bev=0.004)
    K.cyl(name + " stick", (x, y, z), 0.014, 0.18, hw_wood("torch stick", "#5A3E24", "#6E5030", scale=6), rot=(-face * 0.25, 0, 0), v=12, bev=0.003)
    K.cyl(name + " wrap", (x, y - face * 0.02, z + 0.09), 0.022, 0.05, K.mat("torch wrap", "#4A3828", rough=0.9), v=12, bev=0.004)
    fl = K.sph(name + " flame", (x, y - face * 0.025, z + 0.15), 1.0, K.mat("torch flame", "#FFB040", rough=0.3, emit=14.0), scale=(0.024, 0.024, 0.06))
    ld = bpy.data.lights.new(name + " light", 'POINT'); ld.energy = 14; ld.color = (1.0, 0.66, 0.32); ld.shadow_soft_size = 0.08
    o = bpy.data.objects.new(name + " light", ld); o.location = (x, y - face * 0.12, z + 0.17); bpy.context.collection.objects.link(o)
    return fl


def s4_pot(name):
    """a tomb honey pot: a round clay body, a neck and a lip, painted bands, thick dust on its shoulders, a wax seal
    over the mouth (two halves, so it can crack), and the honey under it, still perfect"""
    root = K.empty(name, (0, 0, 0))
    clay = hw_noise("tomb clay", "#A65E32", "#C27A48", scale=9, rough=0.85, bump=0.35)
    band = K.mat("pot band", "#3A2A1E", rough=0.8)
    K.sph(name + " body", (0, 0, 0.12), 1.0, clay, scale=(0.1, 0.1, 0.12), seg=40, ring=20, parent=root)
    K.cyl(name + " foot", (0, 0, 0.012), 0.055, 0.024, clay, v=32, bev=0.004, parent=root)
    K.cyl(name + " neck", (0, 0, 0.215), 0.05, 0.05, clay, v=32, bev=0.004, parent=root)
    K.cyl(name + " lip", (0, 0, S4_PH0 - 0.006), 0.058, 0.014, clay, v=32, bev=0.005, parent=root)
    for z, r in ((0.075, 0.093), (0.15, 0.094)):
        K.cyl(name + " band", (0, 0, z), r + 0.002, 0.012, band, v=40, bev=0.002, parent=root)
    hon = K.cyl(name + " honey", (0, 0, S4_PH0 - 0.004), 0.046, 0.006, hw_honey("tomb honey", "#E8A22A", glow=1.2), v=32, bev=0.001, parent=root)
    dust = hw_noise("thick dust", "#7A705F", "#9E937D", scale=30, rough=1.0, bump=0.8)
    sh = K.sph(name + " dust", (0, 0, 0.13), 1.0, dust, scale=(0.104, 0.104, 0.122), seg=40, ring=20, parent=root)
    wax = K.mat("wax seal", "#8A2A1E", rough=0.45)
    halves = []
    for s in (-1, 1):
        e = K.empty(name + f" seal {s}", (s * 0.03, 0, S4_PH0 + 0.009), parent=root)
        K.cyl(name + " wax", (s * 0.03, 0, S4_PH0 + 0.009), 1.0, 0.016, wax, v=32, bev=0.004, parent=e).scale = (0.032, 0.062, 1.0)
        halves.append(e)
    hw_local(root)
    for e in halves:
        for c in e.children: c.location -= e.location
    return dict(root=root, honey=hon, dust=sh, seal=halves)


def s4_mummy(name, hip):
    """a mummy, lying in its sarcophagus: wrapped in linen strips, a head with two dark eye slits; it sits up at its
    hip and reaches out an arm. Returns dict(root, torso, arm, hand(t-free fn), meshes)."""
    linen = hw_noise("mummy linen", "#CDBF9A", "#A8966E", scale=14, rough=0.95, bump=0.9, stretch=(1, 1, 7), lo=0.3, hi=0.7)
    root = K.empty(name, tuple(hip))
    torso = K.empty(name + " torso", (0, 0, 0), parent=root)
    K.capsule(name + " chest", Vector((0, 0, 0.04)), Vector((0, 0, 0.27)), 0.075, linen, parent=torso, ra=0.07, rb=0.085)
    K.sph(name + " head", (0, -0.01, 0.38), 1.0, linen, scale=(0.065, 0.07, 0.075), parent=torso)
    slit = K.mat("mummy eye", "#1C140E", rough=0.9)
    for s in (-1, 1):
        K.sph(name + " eye", (s * 0.024, -0.066, 0.39), 1.0, slit, scale=(0.014, 0.006, 0.006), parent=torso)
    for z in (0.08, 0.15, 0.22, 0.31, 0.42):
        K.cyl(name + " strip", (0, 0, z), 0.08 if z < 0.3 else 0.068, 0.008, K.mat("mummy strip", "#B8A27A", rough=0.95), v=20, bev=0.002, parent=torso).rotation_euler = (0.25, 0.15, 0)
    arms = []
    for s in (-1, 1):
        a = K.empty(name + f" arm {s}", (s * 0.09, 0, 0.27), parent=torso)
        K.capsule(name + " arm", Vector((s * 0.09, 0, 0.27)), Vector((s * 0.09, 0, 0.03)), 0.028, linen, parent=a)
        K.sph(name + " hand", (s * 0.09, 0, 0.02), 0.03, linen, parent=a)
        arms.append(a)
    for s in (-1, 1):            # legs lie out toward the lens, in the box
        K.capsule(name + " leg", Vector((s * 0.04, 0, 0)), Vector((s * 0.035, -0.28, 0)), 0.04, linen, parent=root)
    hw_local(root)
    for a in arms:
        for c in a.children: c.location -= a.location
    return dict(root=root, torso=torso, arms=arms)


def place_museum():
    """THE VILLAGE MUSEUM'S EGYPTIAN ROOM: sandstone flags, walls cut with hieroglyph rows and painted gods, torches
    of warm light, a gilded sarcophagus open on the floor with its lid propped on the wall, a glass case open at the
    front on a stone plinth, jars and statues on shelves round the walls."""
    rnd = hw_random.Random(44)
    flag = hw_noise("sandstone flags", "#A88A5E", "#D2B386", scale=6, rough=0.9, bump=1.0, detail=8)
    joint = K.mat("flag joint", "#5E4A30", rough=0.95)
    K.box("museum floor", (0, 0.5, -0.01), (8, 8, 0.02), flag, bev=0)
    for k in range(-12, 13):
        K.box("flag joint", (k * 0.32, 0.5, 0.0006), (0.012, 8, 0.0012), joint, bev=0)
    for k in range(-12, 13):
        K.box("flag joint", (0.0, k * 0.32 + 0.16 * (k % 2), 0.0006), (8, 0.012, 0.0012), joint, bev=0)
    wall = hw_noise("sandstone wall", "#B07E50", "#DDB27C", scale=3.5, rough=0.92, bump=1.4, detail=9)
    K.box("museum back wall", (0, 1.25, 1.2), (5, 0.1, 2.4), wall, bev=0)
    K.box("museum side wall", (-1.5, 0.3, 1.2), (0.1, 2.4, 2.4), wall, bev=0)
    K.box("museum side wall", (1.9, 0.3, 1.2), (0.1, 2.4, 2.4), wall, bev=0)
    course = K.mat("stone course", "#7E5C3A", rough=0.95)
    for k in range(8):                          # the wall is laid in courses of cut blocks
        z = 0.44 + k * 0.28
        K.box("stone course", (0, 1.199, z), (5, 0.004, 0.008), course, bev=0)
        for j in range(18):
            K.box("stone joint", (-2.4 + j * 0.3 + 0.15 * (k % 2), 1.199, z + 0.14), (0.008, 0.004, 0.28), course, bev=0)
    frieze = K.mat("frieze blue", "#2F5C8C", rough=0.7); ochre = K.mat("frieze ochre", "#B8782E", rough=0.7)
    K.box("frieze", (0, 1.19, 1.62), (5, 0.02, 0.05), frieze, bev=0)
    K.box("frieze", (0, 1.19, 1.68), (5, 0.02, 0.03), ochre, bev=0)
    K.box("dado", (0, 1.19, 0.22), (5, 0.02, 0.44), K.mat("dado red", "#8E3A26", rough=0.85), bev=0)
    s4_glyph_wall("glyphs", -1.4, -0.35, 1.198, 0.5, 1.55, rnd)
    s4_glyph_wall("glyphs", 1.3, 1.85, 1.198, 0.5, 1.55, rnd)
    s4_god("god anubis", -0.15, 1.196, "#A0522D", "#F2EAD8", "#1E1A18", jackal=True)
    s4_god("god ra", 0.45, 1.196, "#A0522D", "#F2EAD8", "#C8962E")
    s4_god("god horus", 1.0, 1.196, "#A0522D", "#F2EAD8", "#2F5C8C", jackal=True)
    for x in (-0.75, 0.75):
        s4_torch(f"torch {x}", x, 1.12, 1.15, 1)
    # the sarcophagus: a gilded box on the floor, open, the mummy in it; its lid stands against the wall
    gold = hw_noise("sarcophagus gold", "#C8952E", "#E8BE4E", scale=8, rough=0.3, bump=0.25)
    for m in (gold,):
        bs = m.node_tree.nodes["Principled BSDF"]; bs.inputs["Metallic"].default_value = 0.75
    blue = K.mat("sarcophagus blue", "#24508A", rough=0.5)
    cx, cy = S4_HIP.x, S4_HIP.y + 0.12
    L, Wd, H = 0.86, 0.34, 0.24
    K.box("sarcophagus floor", (cx, cy, 0.05), (Wd, L, 0.1), gold, bev=0.01)
    for s in (-1, 1):
        K.box("sarcophagus side", (cx + s * (Wd / 2 - 0.02), cy, H / 2), (0.04, L, H), gold, bev=0.01)
        K.box("sarcophagus band", (cx + s * (Wd / 2 + 0.001), cy, H * 0.7), (0.004, L * 0.96, 0.03), blue, bev=0)
        K.box("sarcophagus end", (cx, cy + s * (L / 2 - 0.02), H / 2), (Wd, 0.04, H), gold, bev=0.01)
    for k in range(7):
        K.box("sarcophagus stripe", (cx - Wd / 2 - 0.001, cy - L / 2 + 0.08 + k * 0.115, H * 0.45), (0.004, 0.05, 0.13), blue, bev=0)
    lid = K.empty("sarcophagus lid", (cx + 0.55, 1.05, 0.0))
    K.box("lid board", (cx + 0.55, 1.05, 0.5), (0.36, 0.06, 1.0), gold, bev=0.03, parent=lid)
    K.sph("lid face", (cx + 0.55, 1.01, 0.88), 1.0, gold, scale=(0.1, 0.04, 0.12), parent=lid)
    K.box("lid headdress", (cx + 0.55, 1.015, 0.8), (0.26, 0.03, 0.22), blue, bev=0.02, parent=lid)
    for k in range(5):
        K.box("lid stripe", (cx + 0.55, 1.012, 0.2 + k * 0.1), (0.3, 0.02, 0.03), blue if k % 2 else gold, bev=0.004, parent=lid)
    hw_local(lid); lid.rotation_euler = (math.radians(-8), 0, 0)
    # the case: a stone plinth with the glass case round it, open at the front
    stone = hw_noise("plinth stone", "#BBA684", "#D2BE9A", scale=12, rough=0.85, bump=0.3)
    K.box("plinth", (S4_POT.x, S4_POT.y, S4_PL / 2), (0.16, 0.16, S4_PL), stone, bev=0.01)
    K.box("plinth cap", (S4_POT.x, S4_POT.y, S4_PL - 0.008), (0.19, 0.19, 0.016), stone, bev=0.006)
    glass = hw_glass("case glass")
    for s in (-1, 1):
        K.box("case side", (S4_POT.x + s * 0.092, S4_POT.y, S4_PL + 0.15), (0.006, 0.17, 0.28), glass, bev=0.001)
    brass = K.mat("case brass", "#B89040", rough=0.35, metal=0.8)
    for s in (-1, 1):
        K.box("case post", (S4_POT.x + s * 0.092, S4_POT.y - 0.085, S4_PL + 0.15), (0.012, 0.012, 0.28), brass, bev=0.002)
    K.text("case card", "TOMB HONEY\n3,000 YEARS", (S4_POT.x - 0.065, S4_POT.y - 0.082, S4_PL - 0.05), 0.014, (math.pi / 2, 0, 0),
           K.mat("card ink", "#2A2018", rough=0.6))
    # shelves of tomb jars and little statues along the left wall and the back
    shelf = hw_wood("museum shelf", "#5E4430", "#7A5A3E", scale=4)
    for z in (0.55, 0.95):
        K.box("museum shelf", (-1.4, 0.4, z), (0.16, 1.4, 0.03), shelf, bev=0.004)
        for k in range(7):
            y = -0.15 + k * 0.19
            K.sph("tomb jar", (-1.4, y, z + 0.08), 1.0, hw_noise("tomb clay", "#A65E32", "#C27A48"), scale=(0.05, 0.05, 0.07), seg=20, ring=10)
            K.cyl("tomb jar lid", (-1.4, y, z + 0.155), 0.025, 0.02, blue if k % 2 else gold, v=16)
    # a big seated statue at the back right
    K.box("statue throne", (1.45, 0.95, 0.3), (0.4, 0.4, 0.6), stone, bev=0.02)
    K.capsule("statue body", Vector((1.45, 0.95, 0.6)), Vector((1.45, 0.95, 1.05)), 0.14, stone)
    K.sph("statue head", (1.45, 0.92, 1.22), 0.1, stone)
    K.box("statue headdress", (1.45, 0.95, 1.2), (0.26, 0.16, 0.22), blue, bev=0.03)

    def light():
        sc = bpy.context.scene; w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
        bg = w.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value = (1.0, 0.86, 0.66, 1); bg.inputs["Strength"].default_value = 0.35
        LOC._area("museum fill", (0.6, -1.6, 2.0), 2.4, 60, (1.0, 0.9, 0.78), aim=(0.0, 0.4, 0.4))
        LOC._area("case spot", (S4_POT.x + 0.2, S4_POT.y - 0.3, 1.7), 0.4, 26, (1.0, 0.95, 0.85), aim=tuple(S4_MOUTH))
        LOC._area("room bounce", (-0.6, 0.9, 2.2), 2.0, 40, (1.0, 0.82, 0.6), aim=(0.0, 0.6, 0.0))
        return LOC._hero_key()
    return light


def shot4():
    """STILL PRESERVED. The lens high, looking down on him at the case: he blows a cloud of thick dust off a sealed
    clay pot from a tomb, cracks its wax with his dipper, and lifts out a shining golden ribbon of honey; behind him
    the mummy sits up in its sarcophagus and reaches for it, and he turns and hands the mummy the dipper."""
    T_BLOW = 0.08 * DUR
    T_CRACK = 0.3 * DUR
    T_LIFT = 0.5 * DUR
    T_UP = 0.68 * DUR
    T_GIVE = 0.86 * DUR
    light = place_museum()
    pot = s4_pot("tomb pot"); pot["root"].location = (S4_POT.x, S4_POT.y, S4_PL); pot["root"].scale = (S4_PK,) * 3
    mum = s4_mummy("mummy", S4_HIP)
    data = load_data()
    data.EXPRESSIONS = dict(data.EXPRESSIONS); data.EXPRESSIONS["blow"] = dict(smile=0.0, open=0.0, oh=1.0, brow=0.2, lid=0.3)
    P0 = S4_P0.copy(); YAW = S4_YAW
    data.place(P0.x, P0.y, math.degrees(YAW))
    hat = bee_hat(data)
    W = hw_win
    sides = sorted("LR", key=lambda s: acts._shoulder(data, s).x)        # [toward -X, toward +X: the mummy's side]
    free, dip_side = sides
    # ---- the mummy: lying flat, sits up at T_UP, its near arm comes up and reaches for the dipper
    tor, arm = mum["torso"], mum["arms"][0]
    T_TAKE = T_GIVE + 0.25
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        up = W(t, T_UP - 0.35, 0.55)
        tor.rotation_euler = (math.radians(-88 + 72 * up + 3 * math.sin(2 * math.pi * t / 1.7) * up), 0, math.radians(-12) * up)
        tor.keyframe_insert("rotation_euler", frame=f)
        reach_ = W(t, T_UP, 0.5)
        take = W(t, T_TAKE, 0.4)
        arm.rotation_euler = (math.radians(-45 * reach_ - 20 * take), math.radians(78 * reach_ - 25 * take), 0)
        arm.keyframe_insert("rotation_euler", frame=f)
        mum["arms"][1].rotation_euler = (math.radians(-15 * reach_), math.radians(20 * up), 0); mum["arms"][1].keyframe_insert("rotation_euler", frame=f)
    def mhand(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return arm.matrix_world @ Vector((0, 0, -0.27))
    # ---- his body: leans in over the case, blows, up on the dipper, down to crack, back with the ribbon, round to the mummy
    def body(t):
        p = P0.copy()
        p += Vector((-0.03, 0.06, 0.0)) * W(t, T_BLOW + 0.3, 0.3) * (1 - W(t, T_CRACK - 0.6, 0.4))     # back out of the dust, coughing
        p.z += 0.02 * hw_kick(t - T_BLOW - 0.35, 0.12)
        p.z += 0.03 * W(t, T_CRACK - 0.6, 0.3) * (1 - W(t, T_CRACK - 0.05, 0.08))                 # up on his toes
        p.z -= 0.02 * hw_kick(t - T_CRACK, 0.1)
        p += Vector((0.0, 0.04, 0.0)) * W(t, T_LIFT - 0.1, 0.5) * (1 - W(t, T_GIVE - 0.5, 0.4))     # leans back with the ribbon
        p += Vector((0.04, 0.05, 0.0)) * hw_kick(t - T_UP - 0.15, 0.2)                             # jumps at the mummy
        p.z += 0.03 * hw_kick(t - T_UP - 0.15, 0.12)
        p += Vector((0.0, 0.03, 0.0)) * W(t, T_GIVE - 0.55, 0.45)
        p.z += 0.04 * hw_kick(t - T_TAKE - 0.25, 0.13)                                            # a hop: bon appetit
        p += S4_FW * (-0.09 * (1 - W(t, 0.05, 0.4)) + 0.03 * hw_kick(t - T_BLOW + 0.08, 0.12))            # steps in, and into the blow
        p.z += 0.035 * W(t, T_CRACK + 0.4, 0.25) * (1 - W(t, T_CRACK + 0.75, 0.25))                   # up on his toes: a sniff
        p += Vector((0.03, -0.0, 0.0)) * W(t, T_CRACK + 0.3, 0.3) * (1 - W(t, T_LIFT - 0.35, 0.3))   # crouches to peer in                                 # steps to the mummy
        yaw = YAW + math.radians(8) * W(t, T_CRACK - 0.6, 0.4) * (1 - W(t, T_CRACK + 0.3, 0.3)) \
            + math.radians(18) * hw_kick(t - T_UP - 0.15, 0.25) + math.radians(40) * W(t, T_GIVE - 0.9, 0.85) \
            - math.radians(30) * W(t, T_TAKE + 0.15, 0.4) + math.radians(7) * math.sin(2 * math.pi * (t - T_CRACK - 0.3) / 0.5) * W(t, T_CRACK + 0.3, 0.2) * (1 - W(t, T_LIFT - 0.4, 0.2))
        return p, yaw
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; p, yaw = body(t); data._kobj(t, loc=tuple(p), rot=yaw)
    hw_layer(data, "spine", lambda t: (5 * W(t, 0.0, 0.3) - 14 * W(t, T_CRACK + 0.4, 0.25) * (1 - W(t, T_CRACK + 0.75, 0.25)) + 4 * W(t, T_CRACK + 0.3, 0.3) * (1 - W(t, T_LIFT - 0.35, 0.3)) * (1 - W(t, T_LIFT, 0.4)) + 6 * hw_kick(t - T_BLOW, 0.12) + 8 * hw_kick(t - T_CRACK, 0.1)
                                      - 10 * W(t, T_LIFT, 0.4) * (1 - W(t, T_UP, 0.3)) - 10 * hw_kick(t - T_UP - 0.15, 0.2)
                                      + 6 * W(t, T_GIVE - 0.4, 0.4), 0, 0), 0, DUR + 0.4)
    # ---- his hands: the free one rests, fans the dust away, opens at the ribbon, throws up at the mummy, spreads;
    # the dipper hand works over the pot with the dipper's head (0.14 m past his fist) doing the job
    fk = [(0.0, (0.07, 0.12, -0.08)), (T_BLOW + 0.1, (0.1, 0.06, -0.12)),
          (T_BLOW + 0.55, (0.13, 0.08, -0.06)), (T_BLOW + 0.85, (0.12, 0.13, -0.07)), (T_BLOW + 1.15, (0.13, 0.07, -0.05)),   # fans the dust away
          (T_CRACK + 0.2, (0.1, 0.07, -0.12)), (T_LIFT - 0.1, (0.1, 0.07, -0.12)),
          (T_LIFT + 0.35, (0.12, 0.11, -0.03)), (T_UP + 0.25, (0.07, 0.13, 0.05)), (T_GIVE - 0.3, (0.09, 0.08, -0.12)),
          (T_TAKE + 0.35, (0.07, 0.16, 0.04)), (DUR + 0.3, (0.07, 0.16, 0.03))]
    data.reach(free, hw_hand(data, free, fk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.35)
    def short(t, world, by=0.13):               # his fist where the dipper's head reaches `world`
        v = Vector(hw_rel(data, dip_side, t, world)); return tuple(v * max(0.3, (v.length - by) / v.length))
    dk = [(0.0, (0.09, 0.1, -0.1)), (T_BLOW + 0.3, (0.11, 0.06, -0.03)), (T_CRACK - 0.7, (0.1, 0.1, -0.02)),
          (T_CRACK - 0.36, (0.07, 0.15, 0.03)),                                   # up for the strike
          (T_CRACK, (0.12, 0.05, -0.05)), (T_CRACK + 0.3, (0.11, 0.03, -0.02)),    # down on the wax
          (T_CRACK + 0.5, (0.12, -0.01, -0.04)), (T_LIFT - 0.5, (0.115, 0.05, -0.035)), (T_LIFT - 0.2, (0.12, 0.01, -0.04)),
          (T_LIFT + 0.15, (0.115, 0.07, -0.02)),   # stirs it
          (T_LIFT + 0.55, (0.1, 0.13, 0.02)), (T_UP, (0.1, 0.14, 0.03)), (T_UP + 0.3, (0.09, 0.14, 0.0))]
    tk = tuple(Vector(short(T_GIVE, mhand(T_GIVE) + Vector((0, 0, 0.02)))) + Vector((0, 0.03, -0.03)))
    dk += [(T_GIVE - 0.45, tuple((Vector((0.09, 0.14, 0.0)) + Vector(tk)) / 2)), (T_GIVE + 0.1, tk), (T_TAKE + 0.05, tk), (T_TAKE + 0.5, tuple(Vector(tk) + Vector((-0.03, 0.03, 0.03)))), (DUR + 0.3, tuple(Vector(tk) + Vector((-0.035, 0.035, 0.035))))]
    data.reach(dip_side, hw_hand(data, dip_side, dk), 0.0, DUR + 0.3, lead=0.05, back=None, elbow_out=0.55)
    # ---- the face
    CAM4 = Vector((S4_P0.x + 0.28, S4_P0.y - 1.45, 1.05))
    data.look_at(S4_MOUTH, 0.0, max_yaw=40, max_pitch=25, blend=0.0)
    data.look_at(CAM4, T_BLOW + 0.4, max_yaw=45, blend=0.15)                                   # coughs at us
    data.look_at(S4_MOUTH + Vector((0.05, 0.02, 0.22)), T_CRACK - 0.45, max_yaw=40, max_pitch=45, blend=0.15)
    data.look_at(S4_MOUTH, T_CRACK - 0.1, max_yaw=40, max_pitch=28, blend=0.1)
    data.look_at(S4_MOUTH + Vector((0, 0, 0.2)), T_LIFT, max_yaw=40, max_pitch=45, blend=0.2)
    data.look_at(mhand(T_UP + 0.3) + Vector((0, 0, 0.15)), T_UP + 0.1, max_yaw=50, max_pitch=40, blend=0.12)
    data.look_at(CAM4, T_UP + 0.7, max_yaw=45, blend=0.2)
    data.look_at(mhand(T_GIVE), T_GIVE - 0.45, max_yaw=50, max_pitch=40, blend=0.2)
    data.look_at(CAM4, T_TAKE + 0.3, max_yaw=45, blend=0.2)
    data.expression("determined", 0.0, T_BLOW - 0.15)
    data.expression("blow", T_BLOW - 0.1, T_BLOW + 0.5, blend=0.1)
    data.expression("wry", T_BLOW + 0.5, T_CRACK - 0.6, blend=0.12)
    data.expression("determined", T_CRACK - 0.55, T_LIFT - 0.1, blend=0.15)
    data.expression("pleased", T_LIFT, T_UP + 0.05, blend=0.15)
    data.expression("surprised", T_UP + 0.1, T_GIVE - 0.5, blend=0.1)
    data.expression("happy", T_GIVE - 0.4, DUR + 1.0, blend=0.2)
    data.finish()
    # ---- his dipper rides his hand, then the mummy's once it takes it
    dip = honey_dipper("honey dipper")
    hw_ride(dip["root"], data, dip_side, fore=True)
    dr = dip["root"]
    for f in range(F(T_LIFT - 0.3), F(T_GIVE - 0.1) + 1):    # up goes the dipper, head high, the ribbon hanging off it
        t = (f - 1) / FPS; u = W(t, T_LIFT - 0.1, 0.4) * (1 - W(t, T_GIVE - 0.7, 0.5))
        if u <= 0: continue
        sc.frame_set(f); bpy.context.view_layer.update()
        M = data.arm.matrix_world @ data.pb["hand." + dip_side].matrix
        p = M.translation + (M.to_3x3() @ Vector((0, 0.05, 0)))
        fore = (M.translation - data.arm.matrix_world @ data.pb["fore." + dip_side].head).normalized()
        yw = data.arm.rotation_euler.z; up = (Vector((0, 0, 1)) + Vector((math.sin(yw), -math.cos(yw), 0)) * 0.35).normalized()
        ax = fore.lerp(up, u).normalized()
        dr.location = p - ax * 0.04; dr.rotation_euler = Vector((0, 0, 1)).rotation_difference(ax).to_euler()
        dr.keyframe_insert("location", frame=f); dr.keyframe_insert("rotation_euler", frame=f)
    for f in range(F(T_TAKE), NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        u = W(t, T_TAKE, 0.15)
        held = dr.matrix_world.translation.copy()
        mh = arm.matrix_world @ Vector((0, 0, -0.27))
        ax = (arm.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        dr.location = held.lerp(mh - ax * 0.03, u); dr.keyframe_insert("location", frame=f)
        if u > 0.5:
            dr.rotation_euler = Vector((0, 0, 1)).rotation_difference(ax).to_euler(); dr.keyframe_insert("rotation_euler", frame=f)
    head = lambda: dr.matrix_world @ Vector((0, 0, dip["head_z"]))
    # ---- the ribbon: a shining strand of honey from the dipper's head down into the pot, folding onto its surface
    rb_m = hw_honey("ribbon honey", "#F0AE2E", glow=2.2, clear=0.3)
    strand = K.cyl("honey ribbon", (0, 0, 0), 1.0, 1.0, rb_m, v=16, bev=0)
    coil = K.cyl("honey fold", (0, 0, 0), 0.03, 0.012, rb_m, v=24, bev=0.004)
    surf = S4_MOUTH + Vector((0, 0, -0.004))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        on = W(t, T_LIFT - 0.3, 0.2) * (1 - W(t, T_GIVE - 0.3, 0.35))
        a = head() + Vector((0, 0, -0.015)); b = surf
        d = a - b; L = max(d.length, 1e-3)
        r = 0.013 * on + 1e-4
        strand.location = (a + b) / 2; strand.scale = (r, r, L)
        strand.rotation_euler = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
        for k in ("location", "scale", "rotation_euler"): strand.keyframe_insert(k, frame=f)
        coil.location = surf + Vector((0, 0, 0.006)); coil.scale = (max(1e-3, on), max(1e-3, on), max(1e-3, on))
        coil.keyframe_insert("location", frame=f); coil.keyframe_insert("scale", frame=f)
    # ---- the dust: thick on the pot until he blows; a cloud of it off the pot and away
    ds = pot["dust"]
    for t, s_ in ((0.0, 1.0), (T_BLOW, 1.0), (T_BLOW + 0.35, 0.001)):
        ds.scale = (0.104 * s_ + (1 - s_) * 0.09, 0.104 * s_ + (1 - s_) * 0.09, 0.122 * max(s_, 0.01)); ds.keyframe_insert("scale", frame=F(t))
    rnd = hw_random.Random(9)
    puff_m = K.mat("dust puff", "#B9AE98", rough=1.0)
    puffs = []
    for k in range(26):
        th = rnd.uniform(0, 2 * math.pi); zz = rnd.uniform(0.06, 0.22)
        start = Vector((S4_POT.x + 0.068 * math.cos(th), S4_POT.y + 0.068 * math.sin(th), S4_PL + zz * S4_PK))
        go = Vector((math.cos(th) * 0.8, math.sin(th) * 0.3 - 0.25, rnd.uniform(0.3, 0.8))).normalized() * rnd.uniform(0.1, 0.2)
        s0 = rnd.uniform(0.014, 0.026)
        pf = K.sph("dust puff", tuple(start), 1.0, puff_m, seg=10, ring=6); puffs.append(pf)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = max(0.0, min(1.0, (t - T_BLOW - rnd.uniform(0, 0.05)) / 0.9))
            pf.location = start + go * (1 - (1 - u) ** 2); g = (0.0 if t < T_BLOW else s0 * (1 + 2.5 * u) * (1 - u) ** 0.6) + 1e-4
            pf.scale = (g, g, g); pf.keyframe_insert("location", frame=f); pf.keyframe_insert("scale", frame=f)
    # ---- the wax cracks under the dipper: two halves tip off the mouth onto the plinth
    for s, e in zip((-1, 1), pot["seal"]):
        base = e.location.copy()
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = max(0.0, min(1.0, (t - T_CRACK) / 0.4))
            e.location = base + Vector((s * 0.1 * u, -0.03 * u, -0.1 * u * u + 0.03 * math.sin(math.pi * u)))
            e.rotation_euler = (0, s * math.radians(100) * u, 0)
            e.keyframe_insert("location", frame=f); e.keyframe_insert("rotation_euler", frame=f)
    CAM = CAM4; LOOK = Vector((S4_P0.x + 0.25, S4_P0.y - 0.05, 0.42))
    cam = K.camera(tuple(CAM), tuple(LOOK), lens=30, fstop=8.0)
    camera_path(cam, lambda t: (CAM + Vector((0.08, 0.06, -0.06)) * ease(t / DUR), LOOK + Vector((0.08, 0.04, 0.02)) * ease(t / DUR), S4_MOUTH))
    return dict(lanes=[], kiosks=[], place="museum_tomb", light=light, data=data, rest=1, grips=("honey dipper", "tomb pot", "mummy hand"),
                conseq=[("a shining golden ribbon of honey from a tomb pot thousands of years old", lambda: meshes([pot["root"], strand, dr]) + [o for o in bpy.data.objects if o.name.startswith(("plinth", "case side"))], T_LIFT - 0.1, T_UP, {"hero": True}),
                        ("he blows a cloud of dust off the sealed pot", lambda: puffs, T_BLOW + 0.05, T_BLOW + 0.7, {"moves": True}),
                        ("the mummy sits up and reaches for it", lambda: meshes([mum["root"]]), T_UP - 0.2, DUR, {"moves": True})])
