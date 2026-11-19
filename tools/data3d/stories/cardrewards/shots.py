"""THE CARD REWARDS SHORT, REBUILT (2026-11-18): every time you pay cash, you pay for someone else's credit card
rewards (Boston Fed, Schuh/Shy/Stavins 2010).

The first cut was refused by caaleb as "lazy as shit": five beats of Data centred behind a counter, one lens, the same
gold card in four of them, watching coins move by themselves. This cut builds every beat new: its own place, its own
camera, its own machine, and Data DRIVES the machine with his body (store/variety.py holds all of it):

  1 hook      store      medium    he slaps his cash on the counter and a giant gold card swallows it note by note
  2 the fee   stockroom  profile   he works a floor pump and a red price tag swells like a balloon
  3 $149      kitchen    high      he shovels his family's coin heap into the card users' POINTS sack
  4 uphill    bank       wide      he cranks a conveyor that carries coins from a tin bucket up into a VIP vault
  5 question  crossroads close     he flips a giant coin, CASH on one face and CARD on the other

Run through the shot harness (store/shots.py, STORY=cardrewards). The props are store/cash_kit.py."""
import cash_kit as XK
import locations as LOC
from mathutils import Euler

US = Vector((0.0, -1.3, 0.62))


def place(name):
    return dict(lanes=[], kiosks=[], place=name, light=LOC.PLACES[name]())


def store_set():
    lanes, kiosks, clerks = build_set([2.4, 3.0], ())
    return dict(lanes=lanes, kiosks=list(kiosks.values()), place="store")


def soft_key(name, at, aim, energy=30, size=26, color=(1.0, 0.95, 0.86)):
    ld = bpy.data.lights.new(name, 'SPOT'); ld.energy = energy; ld.spot_size = math.radians(size); ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.15; ld.color = color
    o = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(o); o.location = at
    o.rotation_euler = (Vector(aim) - Vector(at)).to_track_quat('-Z', 'Y').to_euler()
    return o


def sides(data):
    """(image-left hand, image-right hand) for the shot's camera on -Y"""
    sc.frame_set(1); bpy.context.view_layer.update()
    l, r = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    return l, r


def path(keys):
    """piecewise eased path through (t, Vector) keys"""
    def fn(t):
        if t <= keys[0][0]: return Vector(keys[0][1])
        for (ta, a), (tb, b) in zip(keys, keys[1:]):
            if t <= tb: return Vector(a).lerp(Vector(b), ease((t - ta) / max(1e-6, tb - ta)))
        return Vector(keys[-1][1])
    return fn


def camera(C0, L0, C1, L1, t_end, focus, lens=32, fstop=5.0):
    cam = K.camera(tuple(C0), tuple(L0), lens=lens, fstop=fstop)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / t_end))), L0.lerp(L1, ease(min(1.0, t / t_end))), Vector(focus)))
    return cam


def key_all(o, f, loc=None, rot=None, scale=None):
    if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
    if rot is not None: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)
    if scale is not None: o.scale = scale; o.keyframe_insert("scale", frame=f)


def glow_keys(m, keys):
    b = m.node_tree.nodes["Principled BSDF"]; inp = b.inputs.get("Emission Strength")
    col = b.inputs.get("Emission Color") or b.inputs.get("Emission")
    if col is not None: col.default_value = (1.0, 0.85, 0.4, 1)
    for t, v in keys:
        inp.default_value = v; inp.keyframe_insert("default_value", frame=max(1, F(t)))


# ================================================================ SHOT 1: the hook
def shot1():
    """HE SLAPS HIS CASH ON THE COUNTER AND A GIANT GOLD CARD SWALLOWS IT, NOTE BY NOTE. Medium, at the checkout:
    Data behind the bagging counter slaps a fat wad of notes down beside a giant gold rewards card standing on the
    counter; the notes whip up off the wad one after another, arc over and drop into the slot in the card's top edge,
    which flashes with every one, until the counter is bare. He flings a hand at the card and glares at us."""
    where = store_set()
    TOP = 0.32
    K.box("bagging counter", (-0.06, -0.22, TOP / 2), (1.06, 0.36, TOP), K.mat("bagging steel", "#9EA6AD", rough=0.28, metal=0.85), bev=0.01)
    K.box("bagging edge", (-0.06, -0.402, TOP - 0.01), (1.06, 0.012, 0.024), K.mat("bagging trim", "#2B2B2E", rough=0.4), bev=0.004)
    data = load_data(); data.place(0.08, 0.055, 0)
    L, R = sides(data)
    W = Vector((-0.02, -0.1, TOP))
    import props as _P
    notes = XK.wad("cash wad", tuple(W), n=24, mesh=_P.bill_mesh("cash wad note", w=0.19, h=0.086))   # a FAT wad of big notes
    # the card stands ON THE COUNTER beside the wad, big and whole, and SWALLOWS the notes straight off it: each one
    # whips up in an arc and down into its slot. No tube, no nozzle (11-19, three rounds: a tube and nozzle read as
    # "a coiled horn and a red cone", hid the card's end, and the notes inside were black flecks)
    CARD = Vector((-0.31, -0.2, TOP))
    card, glow, slot = XK.giant_card("giant card", tuple(CARD), w=0.24, h=0.4)
    SLOT = CARD + slot
    # it OPENS ON THE SLAP: his hand comes down with the wad in it inside the first stills (11-19: the wad was already
    # lying there and his hand slid onto it), the notes bounce, and the sucking starts right after
    T_SLAP = 0.45
    top = W + Vector((0, 0, 0.0035 * len(notes) + 0.012 + 0.015))      # the palm on the wad (Data.PALM)
    UPH = Vector((0.04, 0.0, 0.1))                                       # raised high for the wind-up, clear of his face
    PNT = Vector((-0.11, -0.13, 0.49))                                   # ...then flung out at the card: "THAT took it"
    hp = path([(0.0, top + UPH), (T_SLAP, top), (1.2, top + Vector((0.0, 0.0, 0.004))), (1.75, PNT), (DUR, PNT + Vector((0.01, 0, 0.01)))])
    data.reach(L, hp, 0.0, DUR, back=None, elbow_out=0.3)
    lift = lambda t: (hp(t) - top) if t < T_SLAP else Vector((0, 0, 0))   # the wad rides in his hand till it lands
    T0, T1 = 0.55, DUR - 0.9
    sched = [T0 + (T1 - T0) * i / (len(notes) - 1) for i in range(len(notes))]
    FLY = 0.55                                                          # several big notes in the air at once: a stream
    arrivals = []
    for k, (o, ts) in enumerate(zip(reversed(notes), sched)):        # the top note goes first
        p0 = o.location.copy(); r0 = o.rotation_euler.copy()
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < ts:                                                  # in his hand, slapped down, a bounce, then waits
                b = 0.012 * k / len(notes) * max(0.0, math.sin(min(1.0, (t - T_SLAP) / 0.18) * math.pi)) if t >= T_SLAP else 0.0
                key_all(o, f, loc=p0 + lift(t) + Vector((0, 0, b)), rot=r0, scale=(1, 1, 1))
            elif t < ts + FLY:                                          # whipped up off the wad and down into the slot
                u = (t - ts) / FLY
                c = (p0 + SLOT) / 2 + Vector((0, -0.04, 0.42))           # one high arc OVER the card (in front, a clump hid REWARDS)
                q = p0 * (1 - u) ** 2 + c * 2 * u * (1 - u) + (SLOT + Vector((0, 0, 0.01))) * u * u
                key_all(o, f, loc=q, rot=(1.57 * min(1.0, u * 1.6), 0.5 * math.sin(7 * u), r0.z * (1 - u)), scale=(1, 1, 1))
            else:
                key_all(o, f, loc=SLOT + Vector((0, 0, -0.02)), rot=(1.57, 0, 0), scale=(0, 0, 0))
        arrivals.append(ts + FLY)
    keys = [(0.0, 0.0)]
    for ta in arrivals: keys += [(ta - 0.02, 6.0), (ta + 0.04, 300.0), (ta + 0.3, 30.0)]   # a flash a still can catch
    glow_keys(glow, sorted(keys))
    data.look_at(top, 0.0, max_yaw=25, max_pitch=25, blend=0.0)
    data.look_at(CARD + Vector((0, 0, 0.3)), 1.0, max_yaw=35, max_pitch=25)
    data.look_at(US, 1.9, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.0, 0.8)
    data.perform("angry", 1.6, hold=DUR, arms=False)                  # outraged: leans in at us, ears back, brows slammed down
    data.blink(2.6)
    data.finish()
    soft_key("counter key", (0.55, -0.9, 0.6), (-0.05, -0.05, TOP + 0.2), energy=26, size=40)
    soft_key("card key", (-0.6, -0.9, 1.0), (CARD.x, CARD.y, CARD.z + 0.2), energy=22, size=26)
    camera(Vector((-0.11, -1.36, 0.78)), Vector((-0.11, 0.0, 0.62)), Vector((-0.1, -1.28, 0.77)), Vector((-0.1, 0.0, 0.62)),
           DUR, (-0.14, -0.1, 0.55), lens=30, fstop=6.5)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("his cash flies off the counter into the giant gold card", lambda: meshes(notes) + meshes([card]), T0 + 0.2, DUR,
                         {"hero": True, "moves": lambda: meshes(notes)})])


# ================================================================ SHOT 2: the fee
def shot2():
    """HE WORKS A FLOOR PUMP AND A RED PRICE TAG SWELLS LIKE A BALLOON. Side-on (PROFILE) in the stockroom: Data facing
    image-right, both hands on the T-handle of a tall red floor pump; its black hose runs to a red price-tag balloon
    with a big white "$" tied to a stack of cases. Three hard strokes; with each one the tag swells. A notice behind
    says CARD FEES ADD 2-3% TO ALL PRICES. On the last stroke he turns his head to us, wry."""
    where = place("stockroom")
    DX = -0.27
    data = load_data(); data.place(DX, 0.0, 90)
    PUMP = Vector((DX + 0.08, 0.0, 0.0))
    pump, handle, needle = XK.stirrup_pump("floor pump", tuple(PUMP), h=0.28, yaw=math.radians(90), rod=0.24)
    H0 = handle.location.copy()
    # a stack of three shrink-wrapped cases of stock; the tag is tied to the top one (what every price in the store wears)
    SX, SY = 0.08, -0.22
    for k, (w, col) in enumerate([(0.27, "#2D6FB0"), (0.25, "#3E8E5A")]):              # two: the tag sits low, clear of the notice
        K.box(f"stock case {k}", (SX + 0.006 * k, SY, 0.045 + 0.09 * k), (w, 0.2, 0.086), K.mat(f"case {col}", col, rough=0.75), bev=0.006)
        K.box(f"stock case label {k}", (SX + 0.006 * k, SY - 0.101, 0.045 + 0.09 * k), (w * 0.5, 0.002, 0.04), K.mat("case label", "#F4EEDF", rough=0.6), bev=0)
    # the tag stands nearer the lens than he does, so it can swell big without crowding him
    BAL = Vector((SX, SY - 0.02, 0.18))
    bal, _v = XK.price_balloon("price balloon", tuple(BAL), s=1.0)
    bal.rotation_euler = (0, math.radians(22), 0)                        # hangs tilted, point up, like a shop tag
    bpy.context.view_layer.update()
    NECK = bal.matrix_world @ Vector((-0.15 * 1.0, 0.0, 0.15 * 1.0))      # the tag's pointed end, where the air goes in
    # a fat hose that climbs from the pump's foot up the front of the cases into the tag's neck: the pump visibly
    # feeds the tag (11-19 judge: a thin line along the floor, the tag seemed to swell by itself)
    hose = XK._curve_tube("pump hose", [PUMP + Vector((0.03, -0.03, 0.02)), Vector((PUMP.x + 0.12, -0.12, 0.03)),
                                        Vector((NECK.x - 0.08, SY - 0.1, 0.05)), NECK + Vector((-0.06, -0.02, -0.04)),
                                        NECK + Vector((-0.01, 0.0, 0.0))],
                          0.011, XK._mat("pump black", "#1A1A1D", rough=0.5))
    STROKES = [0.7, 2.2, 3.7]                                         # back to back (a pause at the top read as a hitch), slow and heavy
    PERIOD = 1.5
    DOWN, DWELL, UPS = PERIOD / 2, 0.0, PERIOD / 2
    TRAVEL = 0.16                                                       # a HARD stroke a phone can see (11-19 proof: "the handle stays at the same height")
    def stroke(t):
        d = 0.0
        for ts in STROKES:
            if ts <= t < ts + PERIOD: d = 0.5 - 0.5 * math.cos(2 * math.pi * (t - ts) / PERIOD)
        return d
    SCALES = [1.0, 1.18, 1.36, 1.55]
    def swell(t):
        s = SCALES[0]
        for k, ts in enumerate(STROKES):
            if t >= ts: s = SCALES[k] + (SCALES[k + 1] - SCALES[k]) * ease(min(1.0, (t - ts) / DOWN))
        return s
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        key_all(handle, f, loc=H0 - Vector((0, 0, TRAVEL * stroke(t))))
        s = swell(t); key_all(bal, f, scale=(s, s, s))
        key_all(needle, f, rot=(0, math.radians(-60 + 120 * (s - 1.0) / 0.55), 0))
    # the grip ends, in the world: the pump is turned 90 deg so its T-bar runs along Y (one end per hand, side-on)
    def grip(sy):
        return lambda t: PUMP + Vector((0, sy * 0.075, 0.012 + 0.28 * 0.8 + 0.24 - TRAVEL * stroke(t)))   # the palms on the bar
    # facing +X the rig's L side is toward the lens (-Y): L takes the near end of the bar, R the far end
    data.reach("L", grip(-1), 0.0, DUR, back=None, elbow_out=0.35)
    data.reach("R", grip(1), 0.0, DUR, back=None, elbow_out=0.35)
    data.look_at(US, 0.0, max_yaw=40, blend=0.0)
    data.look_at(BAL + Vector((0, 0, 0.1)), 0.3, max_yaw=40, max_pitch=20)
    data.look_at(US, STROKES[-1] + PERIOD * 0.95, max_yaw=75)                    # turned right round from the profile to us
    for f in range(1, NF + 1, 2):                                        # he throws his body into each push (and breathes;
        t = (f - 1) / FPS; d = stroke(t)                                 # idle's own chest keys would fight these)
        data._k('spine', t, rot=(5 * d, 0, 0)); data._k('chest', t, rot=(3 * d - 1.4 * math.sin(2 * math.pi * t / 3.2), 0, 0))
    data.expression("determined", 0.2, STROKES[-1] + PERIOD * 0.7)
    data.expression("wry", STROKES[-1] + PERIOD * 0.8, DUR + 1.0, blend=0.25)
    data.blink(1.3)
    data.finish()
    soft_key("pump key", (-0.6, -1.1, 1.0), (DX + 0.1, 0.0, 0.4), energy=30, size=36)
    soft_key("tag key", (0.6, -0.9, 0.9), (BAL.x, BAL.y, BAL.z + 0.1), energy=16, size=26)
    camera(Vector((-0.04, -1.38, 0.44)), Vector((-0.04, 0.2, 0.42)), Vector((-0.03, -1.32, 0.44)), Vector((-0.03, 0.2, 0.43)),
           DUR, (-0.04, 0.0, 0.42), lens=30, fstop=6.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("each pump stroke swells the red price tag", lambda: meshes([bal]), STROKES[0], DUR, {"hero": True, "moves": lambda: meshes([bal])}),
                        ("the pump handle goes down and up", lambda: meshes([pump, handle]), STROKES[0], STROKES[-1] + DOWN + DWELL + UPS, {"moves": lambda: meshes([handle])})])


# ================================================================ SHOT 3: $149 a year
def shot3():
    """HE SHOVELS HIS FAMILY'S COIN HEAP INTO THE CARD USERS' POINTS SACK. From HIGH above in the kitchen at night:
    a heap of gold coins on the lino with a little "$149 A YEAR" flag in it, Data with a long coal shovel, and a fat
    burlap sack stencilled POINTS. Three scoops: dig, swing, and the coins arc off the blade into the sack. The heap
    shrinks, the sack bulges. He looks up at us, sad."""
    where = place("kitchen")
    data = load_data(); data.place(0.0, 0.16, 0)
    HEAP = Vector((-0.18, -0.16, 0.0))
    heap = XK.coin_heap("coin heap", tuple(HEAP), r=0.2, h=0.17, n=220)
    flag = K.empty("heap flag", (0, 0, 0))                              # built about the origin (absolute spots), then placed
    K.cyl("flag stick", (0, 0, 0.17), 0.004, 0.34, K.mat("flag stick", "#E6DCC6", rough=0.6), bev=0, parent=flag)
    K.box("flag cloth", (0.1, 0, 0.28), (0.2, 0.005, 0.11), K.mat("flag cloth", "#F7F4EC", rough=0.6), bev=0.002, parent=flag)
    K.text("flag text", "$149", (0.1, -0.004, 0.292), 0.062, (math.pi / 2, 0, 0), K.mat("flag ink", "#2B5C2E", rough=0.5), extrude=0.0015, parent=flag)
    K.text("flag text 2", "A YEAR", (0.1, -0.004, 0.247), 0.026, (math.pi / 2, 0, 0), K.mat("flag ink", "#2B5C2E", rough=0.5), extrude=0.0008, parent=flag)
    flag.location = HEAP + Vector((-0.09, 0.02, 0.0))
    SACK = Vector((0.25, -0.25, 0.0))
    sack, mouth = XK.sack("points sack", tuple(SACK), r=0.13, h=0.27)
    MOUTH = SACK + mouth
    inside = bpy.data.objects["points sack gold inside"]                # the sack starts empty and fills scoop by scoop
    IS = inside.scale.copy()
    sheap = XK.coin_heap("sack coins", tuple(MOUTH + Vector((0, 0, -0.005))), r=0.085, h=0.07, n=70, seed=5)   # LOOSE COINS heaping up in its mouth
    shov, grip_l, mid_l = XK.shovel("coal shovel", length=0.32, big=True)   # the blade lands ON the heap and OVER the mouth
    GL = grip_l.z
    SCOOPS = [0.5, 2.0, 3.5]
    DIG, LIFT, DUMP, BACK = 0.35, 0.55, 0.3, 0.4
    # the grip TRAVELS: low and out over the heap to dig, up and across to the sack to dump (11-19 proof: "his shovel
    # hand stays parked at his chest while the blade swings around it ... a puppet")
    G_DIG = Vector((-0.07, 0.05, 0.36)); G_DUMP = Vector((0.06, 0.04, 0.47))      # the D-grip, by his chest (his reach is 0.19 m)
    U_DIG = (G_DIG - (HEAP + Vector((0.04, 0.06, 0.03)))).normalized()
    U_DUMP = (G_DUMP - (MOUTH + Vector((-0.03, 0.03, 0.15)))).normalized()   # the blade tips ABOVE the mouth, not through the sack (11-19)
    def phase(t):
        """0 = in the heap, 1 = over the sack mouth"""
        v = 0.0
        for ts in SCOOPS:
            if ts <= t < ts + DIG: v = 0.0
            elif ts + DIG <= t < ts + DIG + LIFT: v = ease((t - ts - DIG) / LIFT)
            elif ts + DIG + LIFT <= t < ts + DIG + LIFT + DUMP: v = 1.0
            elif ts + DIG + LIFT + DUMP <= t < ts + DIG + LIFT + DUMP + BACK: v = 1 - ease((t - ts - DIG - LIFT - DUMP) / BACK)
        return v
    def pose(t):
        v = phase(t); G = G_DIG.lerp(G_DUMP, v); U = U_DIG.lerp(U_DUMP, v).normalized()
        return G, U, G - U * GL
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; G, U, B = pose(t)
        q = U.to_track_quat('Z', 'Y'); e = q.to_euler()
        tip = 0.0
        for ts in SCOOPS:
            a = ts + DIG + LIFT
            if a <= t < a + DUMP: tip = math.radians(70) * math.sin(math.pi * (t - a) / DUMP)
        shov.location = B; shov.rotation_euler = (q @ Euler((tip, 0, 0)).to_quaternion()).to_euler()
        shov.keyframe_insert("location", frame=f); shov.keyframe_insert("rotation_euler", frame=f)
    L, R = sides(data)
    data.reach(R, lambda t: pose(t)[0], 0.0, DUR, back=None, elbow_out=0.4)   # the wrist past the grip: the mitt round it
    data.reach(L, lambda t: pose(t)[0] - pose(t)[1] * 0.045 + Vector((-0.015, 0, 0)), 0.0, DUR, back=None, elbow_out=0.4)          # two hands apart on the shaft, the way a shovel is held
    # a load of coins rides the blade from the dig to the dump, then flies into the sack
    gold = bpy.data.materials.get("coins")
    load = K.empty("blade load", (0, 0, 0)); load.parent = shov
    K.sph("blade load heap", (0, -0.016, -0.01), 1.0, gold, scale=(0.05, 0.02, 0.055), parent=load)
    flyers = []
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        on = any(ts + DIG * 0.7 <= t < ts + DIG + LIFT + DUMP * 0.4 for ts in SCOOPS)
        load.scale = (1, 1, 1) if on else (0, 0, 0); load.keyframe_insert("scale", frame=f)
    proto = K.cyl("sack coin", (0, 0, -5), 0.03, 0.006, gold, v=20, bev=0.001)   # big enough to see in flight
    rnd = random.Random(3)
    for k, ts in enumerate(SCOOPS):
        a = ts + DIG + LIFT
        for j in range(13):
            o = proto.copy(); bpy.context.collection.objects.link(o); flyers.append(o)
            t0 = a + 0.05 + 0.025 * j; fl = 0.4
            for f in range(1, NF + 1):
                t = (f - 1) / FPS
                u = (t - t0) / fl
                src = pose(a + 0.05)[2]
                dst = MOUTH + Vector((math.cos(j * 2.1) * 0.03, math.sin(j * 2.1) * 0.02, -0.03))
                if u < 0: o.scale = (0, 0, 0); o.location = src
                elif u <= 1: o.scale = (1, 1, 1); o.location = src.lerp(dst, u) + Vector((0, 0, 0.16 * 4 * u * (1 - u))); o.rotation_euler = (8 * u, 5 * u, j)
                else: o.scale = (0, 0, 0); o.location = dst
                o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f); o.keyframe_insert("scale", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; n = sum(1 for ts in SCOOPS if t >= ts + DIG * 0.7)
        h = 1.0 - 0.3 * n
        prev = 1.0 - 0.3 * max(0, n - 1)
        if n and t < SCOOPS[n - 1] + DIG: h = prev + (h - prev) * ease((t - SCOOPS[n - 1] - DIG * 0.7) / (DIG * 0.3))
        hs = 0.3 + 0.7 * h; heap.scale = (hs, hs, hs)                    # a smaller PILE each scoop, never a flat gold plate
        heap.keyframe_insert("scale", frame=f)
        m = sum(1 for ts in SCOOPS if t >= ts + DIG + LIFT + 0.25)
        b = 1.0 + 0.16 * m
        pb_ = 1.0 + 0.16 * max(0, m - 1)
        if m and t < SCOOPS[m - 1] + DIG + LIFT + 0.55: b = pb_ + (b - pb_) * ease((t - SCOOPS[m - 1] - DIG - LIFT - 0.25) / 0.3)
        sack.scale = (b, b, 1.0 + 0.12 * (b - 1.0) / 0.16); sack.keyframe_insert("scale", frame=f)
        g = (b - 1.0) / 0.48
        inside.scale = (0, 0, 0); inside.keyframe_insert("scale", frame=f)   # a smooth gold dome read as an egg in a pan
        k = 0.15 + 0.85 * g; sheap.scale = (k, k, k); sheap.keyframe_insert("scale", frame=f)
        flag.location = HEAP + Vector((-0.09, 0.02, 0.12 * (h - 1.0))); flag.keyframe_insert("location", frame=f)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(HEAP, 0.3, max_yaw=30, max_pitch=14)
    data.look_at(MOUTH, SCOOPS[0] + DIG + 0.1, max_yaw=30, max_pitch=14)
    data.look_at(HEAP, SCOOPS[1], max_yaw=30, max_pitch=14)
    data.look_at(MOUTH, SCOOPS[1] + DIG + 0.1, max_yaw=30, max_pitch=14)
    data.look_at(Vector((0.02, -0.77, 0.9)), DUR - 1.1, max_yaw=20, max_pitch=40)
    for f in range(1, NF + 1, 2):                                        # his back bends into the dig and twists to each end
        t = (f - 1) / FPS; v = phase(t)
        data._k('spine', t, rot=(10 * (1 - v), 0, 8 - 16 * v)); data._k('chest', t, rot=(4 * (1 - v) - 1.4 * math.sin(2 * math.pi * t / 3.2), 0, 4 - 8 * v))
    data.expression("determined", 0.2, DUR - 1.2)
    data.expression("sad", DUR - 1.1, DUR + 1.0, blend=0.25)          # (a slumped head from above hides the face)
    data.blink(1.1)
    data.finish()
    # HIGH, but in close over the heap and the sack, so the money reads big in the near frame
    camera(Vector((0.0, -0.95, 0.92)), Vector((0.0, -0.05, 0.33)), Vector((0.0, -0.9, 0.9)), Vector((0.0, -0.05, 0.33)),
           DUR, (0.0, -0.15, 0.2), lens=22, fstop=6.0)
    return dict(**where, data=data, rest=1, grips=("coal shovel",),
                conseq=[("the coin heap shrinks and the POINTS sack bulges, scoop by scoop", lambda: meshes([heap, sack]), SCOOPS[0], DUR, {"hero": True}),
                        ("each scoop of coins flies off the shovel into the sack", lambda: meshes([shov]) + flyers, SCOOPS[0], SCOOPS[-1] + DIG + LIFT + DUMP,
                         {"moves": lambda: meshes([shov])})])


# ================================================================ SHOT 4: it flows uphill
def shot4():
    """HE CRANKS A CONVEYOR THAT CARRIES COINS FROM A TIN BUCKET UP INTO A VIP VAULT. WIDE in the bank lobby: a dented
    tin bucket of coins on the marble at the foot of a steep cleated belt that climbs to a steel vault up on a plinth,
    "$750" on its face. Data turns the big yellow crank wheel; the belt runs, coin after coin rides up it and drops
    into the vault, whose gold rises. The poor end empties into the rich end, and he is the one turning the handle.
    He looks at us, sour."""
    where = place("bank")
    for o in list(bpy.data.objects):                                    # the lobby's own vault door competed with his vault
        if o.name.startswith(("vault door", "vault ring", "vault hub", "vault spoke")): bpy.data.objects.remove(o)
    # SIDE-ON to the wheel, the way a man turns a crank: he stands at its left facing it, the wheel square to the lens
    # beside him, and the belt runs a long climb across the frame (11-19, four rounds facing us behind it: the wheel
    # read as "a badge or target on his coat")
    DX, DY = -0.38, 0.0
    data = load_data(); data.place(DX, DY, 90)
    L, R = sides(data)
    HUB = Vector((DX + 0.17, DY - 0.03, 0.4))                           # out in front of him at hand height
    A = Vector((-0.05, 0.02, 0.06)); B = Vector((0.26, 0.04, 0.66))
    belt, wheel, cleats, belt_fn, WR = XK.conveyor("money conveyor", A, B, w=0.11, cleats=14, hub=HUB, WR=0.07, knob=0.06,
                                                       cleat_col="#33373C")   # dark cleats: yellow ones read as "paddles or cups", not coins (11-19)
    BK = Vector((A.x - 0.03, A.y - 0.16, 0.0))                           # in front of the belt's foot, clear of the wheel
    bucket = XK.tin_bucket("tin bucket", tuple(BK), r=0.09, h=0.1)
    # a stake sign in front of the bucket, big enough to read on a phone
    SG = Vector((BK.x - 0.12, BK.y - 0.14, 0.0))                        # out front of the bucket, clear of the belt foot and his legs
    # the label is ON the bucket (11-19: a stake sign in front of it hid the bucket)
    YW = 0.0
    nb = Vector((math.sin(YW), -math.cos(YW), 0))
    pb_ = BK + nb * 0.1 + Vector((0, 0, 0.05))
    K.box("poorest board", tuple(pb_), (0.22, 0.006, 0.075), K.mat("poorest card", "#F4EEDF", rough=0.6), bev=0.002).rotation_euler = (0, 0, YW)
    K.text("bucket tag", "POOREST", tuple(pb_ + nb * 0.005), 0.052, (math.pi / 2, 0, YW), K.mat("tag ink dark", "#2B2B2E", rough=0.5), extrude=0.0012)
    bfill = K.cyl("bucket coins", (BK.x, BK.y, 0.05), 0.078, 0.01, bpy.data.materials.get("coins") or K.mat("coins", "#F4CC52", rough=0.22, metal=0.65, emit=0.12), v=32, bev=0.002)
    PL = Vector((B.x + 0.07, B.y + 0.03, 0.0))                          # the belt's head right over the vault's mouth
    PH = 0.26                                                           # a low plinth and a BIG vault: the destination reads
    K.box("vault plinth", (PL.x, PL.y, PH / 2), (0.32, 0.24, PH), K.mat("plinth marble", "#E9E3D8", rough=0.2), bev=0.006)
    ink = K.mat("plinth ink", "#2B2B2E", rough=0.5)
    # the point of the shot is written on the PLINTH, big and below the gold, so the rising fill never covers it (11-19)
    K.text("plinth price", "$750", (PL.x, PL.y - 0.123, PH * 0.66), 0.1, (math.pi / 2, 0, 0), K.mat("plinth gold", "#B8862B", rough=0.3, metal=0.8), extrude=0.002)
    K.text("plinth word", "RICHEST", (PL.x, PL.y - 0.123, PH * 0.36), 0.062, (math.pi / 2, 0, 0), ink, extrude=0.0015)
    vault, fill, vm = XK.vault("vip vault", (PL.x, PL.y, PH), w=0.3, d=0.2, h=0.36, label=None, glass_front=True)
    VM = PL + Vector((0, 0, PH + 0.2))                                # where a coin lands in the vault
    T0, T1 = 0.5, DUR - 0.9
    OMEGA = 2 * math.pi * 0.42                                         # wheel turns per second: a heavy crank (faster turns stutter the arm)
    RAMP = 0.6
    _acc = [0.0]
    for f in range(1, NF + 2):
        t = f / FPS
        r = ease(min(1.0, max(0.0, (t - T0) / RAMP))) * (1 - ease(min(1.0, max(0.0, (t - (T1 - RAMP)) / RAMP))))
        _acc.append(_acc[-1] + OMEGA * r / FPS)
    ang = lambda t: _acc[max(0, min(len(_acc) - 1, int(round(t * FPS))))]
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; wheel.rotation_euler = (0, -ang(t), 0); wheel.keyframe_insert("rotation_euler", frame=f)
    knob = lambda t: HUB + Vector((WR * 0.86 * math.cos(-ang(t)), -0.055, WR * 0.86 * math.sin(ang(t))))
    data.reach(L, knob, 0.0, DUR, back=None, elbow_out=0.35)        # facing +X his L side is toward the lens: the near hand turns it
    SPEED = 0.7                                                         # belt travel per wheel turn, as a fraction of the belt
    pos = lambda t: ang(t) / (2 * math.pi) * SPEED
    for k, c in enumerate(cleats):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (k / len(cleats) + pos(t)) % 1.0
            c.location = belt_fn(u); c.keyframe_insert("location", frame=f)
    gold = bpy.data.materials.get("coins")
    proto = K.cyl("belt coin", (0, 0, -5), 0.038, 0.009, gold, v=24, bev=0.0015)
    N = 18
    starts = [-0.62 + 0.13 * i for i in range(N)]                      # already riding at the start: the vault fills from the first second
    coins = []
    for i, s0 in enumerate(starts):
        o = proto.copy(); bpy.context.collection.objects.link(o); coins.append(o)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = pos(t) - s0
            if u < 0: o.scale = (0, 0, 0); o.location = belt_fn(0.0)
            elif u < 1.0: o.scale = (1, 1, 1); o.location = belt_fn(u) + Vector((0, 0, 0.012)); o.rotation_euler = (0, -math.atan2(B.z - A.z, B.x - A.x), 0)
            else:
                d = min(1.0, (u - 1.0) / 0.1)                           # tips off the top and DROPS into the vault
                o.scale = (1, 1, 1) if d < 1 else (0, 0, 0)
                o.location = B.lerp(VM, d) + Vector((0, 0, 0.05 * 4 * d * (1 - d)))
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f); o.keyframe_insert("scale", frame=f)
    ARRIVE = max(1, sum(1 for s0 in starts if pos(DUR) - s0 >= 1.1))   # the coins that make it this shot fill it to the brim
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        done = sum(min(1.0, max(0.0, (pos(t) - s0 - 1.08) / 0.1)) for s0 in starts)   # each landing raises it smoothly
        fill.scale = (1, 1, 0.06 + 0.9 * min(1.0, done / ARRIVE)); fill.keyframe_insert("scale", frame=f)
        left = sum(1 for s0 in starts if pos(t) - s0 < 0)
        bfill.location.z = 0.012 + 0.11 * left / N        # heaped over the rim at first, so its emptying shows; bfill.keyframe_insert("location", frame=f)
    # he keeps his face to us: a glance at the wheel, the vault, and back (11-19: turned to the belt he showed the
    # lens the back of his head)
    CAM = Vector((0.01, -1.46, 0.79))                                  # the lens
    data.look_at(CAM, 0.0, max_yaw=75, blend=0.0)
    data.look_at(HUB, 0.4, max_yaw=15, max_pitch=25)
    data.look_at(CAM, 1.6, max_yaw=75)
    data.look_at(VM + Vector((0, 0, 0.1)), DUR * 0.45, max_yaw=15, max_pitch=15)
    data.look_at(CAM, DUR * 0.6, max_yaw=75)
    data.idle(0.0, DUR)
    data.expression("determined", 0.2, T1 - 0.3)
    data.expression("angry", T1 - 0.2, DUR + 1.0, blend=0.25)          # sour: narrowed eyes, the mouth turned down
    data.blink(2.4)
    data.finish()
    soft_key("bank key", (-0.7, -1.4, 1.4), (0.0, -0.02, 0.45), energy=40, size=40)
    soft_key("vault key", (0.8, -1.0, 1.2), (PL.x, PL.y, 0.6), energy=16, size=22)
    # WIDE from the left and above, down onto the belt's face: the whole machine runs corner to corner, the bucket at
    # its foot, the vault high on the right, Data turning the wheel (11-18: square-on it was framed like the pump shot;
    # from the right the belt was edge-on, a black line)
    # from his LEFT: the wheel stands out beside his chest instead of on it (11-19, three rounds: "a badge or target on his coat")
    camera(Vector((0.01, -1.52, 0.8)), Vector((0.01, 0.0, 0.42)), Vector((0.01, -1.46, 0.79)), Vector((0.01, 0.0, 0.42)),   # wide enough for all of him (11-19: cut by the left edge)
           DUR, (0.0, -0.02, 0.4), lens=24, fstop=8.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("coins ride the belt up out of the tin bucket into the VIP vault", lambda: meshes([belt, vault]) + coins, T0 + 0.6, DUR,
                         {"hero": True, "moves": lambda: coins}),
                        ("he turns the crank wheel on its post", lambda: meshes([wheel]) + [o for o in bpy.data.objects if o.name.startswith("money conveyor post")], T0, T1,
                         {"moves": lambda: meshes([wheel])})])


# ================================================================ SHOT 5: the question
def shot5():
    """HE FLIPS A GIANT COIN: CASH ON ONE FACE, CARD ON THE OTHER. CLOSE at a country crossroads at golden hour, a
    signpost behind him pointing CASH one way and CARD the other. He holds the big gold coin, tosses it; it spins up
    flashing CASH, CARD, CASH; he catches it and it is still spinning on its edge between his hands. He looks at us:
    which one?"""
    where = place("crossroads")
    # CENTRED in the frame (11-19 judge: off to the left, his head and glasses cut by the frame edge), with headroom
    # above his ears for the toss, and the signpost's two arms ABOVE his head on its right, clear of the coin's arc
    DX = -0.05
    data = load_data(); data.place(DX, 0.1, 0)
    L, R = sides(data)
    post = XK.signpost("crossroads sign", (DX + 0.19, 0.5, 0.0), h=1.75, arm=0.16)
    coin = XK.flip_coin("giant coin", r=0.1, h=0.02)
    C0 = Vector((DX + 0.07, -0.06, 0.44))
    # the toss straddles the middle of the shot, so the middle still has the coin high in the air, half turned
    T_TOSS, T_CATCH = 2.25, 3.85
    PEAK = 1.06                                                       # above his ears, beside his head, all in frame
    OUT = -0.15                                                       # the arc swings out to image-left, off his face
    TURN0, TURN1 = 1.0, 1.5                                           # before the toss he turns it over: CASH -> CARD
    AIR = 8 * math.pi + 1.1                                           # 4.2 turns in the air; at the peak CARD is half turned
    SPIN, SETTLE = 1.5, 4 * math.pi - 0.5                             # after the catch it spins down to CARD at 3/4
    def cpos(t):
        if t < T_TOSS - 0.3: return C0
        if t < T_TOSS: return C0 + Vector((0, 0, 0.055 * math.sin(math.pi * (t - T_TOSS + 0.3) / 1.3) ** 2))
        if t < T_CATCH:
            u = (t - T_TOSS) / (T_CATCH - T_TOSS); z0 = 0.055 * math.sin(math.pi * 0.3 / 1.3) ** 2   # leaves his hands mid-throw
            out = ease(min(1.0, u / 0.14)) * (1 - ease(max(0.0, (u - 0.86) / 0.14)))
            return C0 + Vector((OUT * out + 0.02 * u, 0, z0 * (1 - u) + (PEAK - C0.z) * 4 * u * (1 - u)))
        return C0 + Vector((0.02, 0, 0))
    def crot(t):
        # it turns about the UPRIGHT axis, so each face comes round to the lens the right way up
        if t < T_TOSS: return (0, 0, math.pi * ease(min(1.0, max(0.0, (t - TURN0) / (TURN1 - TURN0)))))
        if t < T_CATCH: return (0, 0, math.pi + AIR * (t - T_TOSS) / (T_CATCH - T_TOSS))
        v = min(1.0, (t - T_CATCH) / SPIN)
        drift = 0.15 * min(1.0, max(0.0, (t - T_CATCH - SPIN) / max(0.1, DUR - T_CATCH - SPIN)))
        return (0, 0, math.pi + AIR + SETTLE * (1 - (1 - v) ** 2) + drift)   # ends CARD-ward, still turning
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; key_all(coin, f, loc=cpos(t), rot=crot(t))
    def hand(sx):
        def fn(t):
            base = C0 + Vector((sx * 0.1 + 0.02 * ease(min(1.0, max(0.0, (t - T_TOSS) / (T_CATCH - T_TOSS)))), -0.005, 0))
            if t < T_TOSS - 0.3: return base
            u = (t - (T_TOSS - 0.3)) / 1.3                                    # the throw: up with the coin, back down to wait for it
            if u >= 1.0: return base
            return base + Vector((0, 0, 0.055 * math.sin(math.pi * u) ** 2))
        return fn
    data.reach(L, hand(-1), 0.0, DUR, back=None, elbow_out=0.5)
    data.reach(R, hand(1), 0.0, DUR, back=None, elbow_out=0.5)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(C0, TURN0 - 0.1, max_yaw=20, max_pitch=25)
    data.look_at(C0 + Vector((OUT, 0, 0.45)), T_TOSS + 0.3, max_yaw=15, max_pitch=30)
    data.look_at(C0, T_CATCH - 0.15, max_yaw=20, max_pitch=25)
    data.look_at(US + Vector((0.05, 0, 0.04)), T_CATCH + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.0, T_TOSS)                        # (pleased is an eye-smile: shut eyes on the first still)
    data.expression("surprised", T_TOSS + 0.1, T_CATCH + 0.3, blend=0.15)
    data.expression("wry", T_CATCH + 0.6, DUR + 1.0, blend=0.25)      # one brow up to the lens: which one?
    data.blink(1.8)
    data.finish()
    camera(Vector((DX + 0.05, -0.72, 0.66)), Vector((DX + 0.05, 0.1, 0.75)), Vector((DX + 0.05, -0.68, 0.66)),
           Vector((DX + 0.05, 0.1, 0.75)), DUR, (DX + 0.05, -0.05, 0.6), lens=26, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("the giant CASH / CARD coin spins up and lands on its edge in his hands", lambda: meshes([coin]), T_TOSS, DUR,
                         {"hero": True, "moves": lambda: meshes([coin])})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


