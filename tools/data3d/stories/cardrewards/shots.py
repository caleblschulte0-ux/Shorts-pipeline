"""THE CARD REWARDS SHORT, REBUILT (2026-11-18): every time you pay cash, you pay for someone else's credit card
rewards (Boston Fed, Schuh/Shy/Stavins 2010).

The first cut was refused by caaleb as "lazy as shit": five beats of Data centred behind a counter, one lens, the same
gold card in four of them, watching coins move by themselves. This cut builds every beat new: its own place, its own
camera, its own machine, and Data DRIVES the machine with his body (store/variety.py holds all of it):

  1 hook      store      low       he slaps his cash on the counter and a vacuum tube sucks it away to a giant gold card
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
    """HE SLAPS HIS CASH ON THE COUNTER AND A VACUUM TUBE SUCKS IT AWAY INTO A GIANT GOLD CARD. A LOW lens at the
    checkout, looking up: Data behind the bagging counter, a fat wad of notes in front of him, a clear pneumatic tube
    hanging over it with a chrome hood, the tube arcing over to a giant gold rewards card standing at the end of the
    counter. He slaps the wad down; the notes lift off one after another, up the tube, over and into the card, which
    flares with every one. He looks at us, outraged."""
    where = store_set()
    TOP = 0.32
    K.box("bagging counter", (0.02, -0.22, TOP / 2), (0.86, 0.36, TOP), K.mat("bagging steel", "#9EA6AD", rough=0.28, metal=0.85), bev=0.01)
    K.box("bagging edge", (0.02, -0.402, TOP - 0.01), (0.86, 0.012, 0.024), K.mat("bagging trim", "#2B2B2E", rough=0.4), bev=0.004)
    data = load_data(); data.place(0.11, 0.055, 0)
    L, R = sides(data)
    W = Vector((-0.04, -0.08, TOP))
    notes = XK.wad("cash wad", tuple(W), n=14)
    CARD = Vector((-0.30, -0.10, TOP))
    card, glow, slot = XK.giant_card("giant card", tuple(CARD), w=0.2, h=0.3)
    SLOT = CARD + slot
    HOOD = W + Vector((0, 0, 0.17))
    tube, along = XK.vacuum_tube("vacuum tube", [HOOD, HOOD + Vector((0.0, 0, 0.3)), Vector((-0.14, -0.09, 0.92)),
                                                 Vector((-0.29, -0.10, 0.8)), SLOT + Vector((0, 0, 0.03))], r=0.04)
    T_SLAP = 0.62
    top = W + Vector((0, 0, 0.0035 * len(notes) + 0.012))
    top = top + Vector((0, 0, 0.045))                                  # the wrist: the mitten's palm lands on the wad, not in the counter
    hp = path([(0.3, top + Vector((0.0, 0.02, 0.07))), (T_SLAP, top), (0.95, top),
               (1.6, top + Vector((0.05, 0.05, 0.0)))])
    data.reach(L, hp, 0.3, DUR, lead=0.3, back=None, elbow_out=0.3)
    T0, T1 = 0.85, DUR - 0.75
    sched = [T0 + (T1 - T0) * i / (len(notes) - 1) for i in range(len(notes))]
    UP, RIDE = 0.14, 0.55
    arrivals = []
    for k, (o, ts) in enumerate(zip(reversed(notes), sched)):        # the top note goes first
        p0 = o.location.copy(); r0 = o.rotation_euler.copy()
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            if t < ts:                                                  # under his slap it squashes flat, then waits
                key_all(o, f, loc=p0, rot=r0, scale=(1, 1, 1))
            elif t < ts + UP:                                           # lifted off the wad into the hood
                u = ease((t - ts) / UP); key_all(o, f, loc=p0.lerp(along(0.0), u), rot=(u * 1.4, 0, r0.z), scale=(1, 1, 1))
            elif t < ts + UP + RIDE:                                    # up the tube and over, fluttering
                u = (t - ts - UP) / RIDE; q = along(u)
                key_all(o, f, loc=q, rot=(1.4 + 6.0 * u, 0.6 * math.sin(9 * u), r0.z), scale=(0.8, 0.8, 0.8))
            else:
                key_all(o, f, loc=SLOT + Vector((0, 0, -0.02)), rot=(1.57, 0, 0), scale=(0, 0, 0))
        arrivals.append(ts + UP + RIDE)
    keys = [(0.0, 0.0)]
    for ta in arrivals: keys += [(ta - 0.02, 0.6), (ta + 0.04, 7.0), (ta + 0.2, 1.2)]
    glow_keys(glow, sorted(keys))
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(top, 0.25, max_yaw=25, max_pitch=25)
    data.look_at(HOOD + Vector((0, 0, 0.3)), 1.0, max_yaw=30, max_pitch=30)
    data.look_at(CARD + Vector((0, 0, 0.25)), 1.9, max_yaw=35, max_pitch=15)
    data.look_at(US, DUR - 1.0, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.2, 1.0)
    data.expression("surprised", 1.0, 1.9, blend=0.15)
    data.expression("alarmed", 2.0, DUR + 1.0, blend=0.2)
    data.blink(1.6)
    data.finish()
    soft_key("counter key", (0.55, -0.9, 0.6), (-0.05, -0.05, TOP + 0.2), energy=26, size=40)
    soft_key("card key", (-0.6, -0.7, 0.7), (CARD.x, CARD.y, TOP + 0.18), energy=14, size=22)
    camera(Vector((0.12, -0.84, 0.37)), Vector((-0.07, 0.0, 0.64)), Vector((0.1, -0.78, 0.37)), Vector((-0.07, 0.0, 0.64)),
           DUR, (-0.05, -0.08, 0.5), lens=22, fstop=5.6)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("his cash is sucked up the tube and into the giant gold card", lambda: meshes(notes) + meshes([tube, card]), T0 + 0.2, DUR,
                         {"hero": True, "moves": lambda: meshes(notes)})])


# ================================================================ SHOT 2: the fee
def shot2():
    """HE WORKS A FLOOR PUMP AND A RED PRICE TAG SWELLS LIKE A BALLOON. Side-on (PROFILE) in the stockroom: Data facing
    image-right, both hands on the T-handle of a tall red floor pump; its black hose runs to a red price-tag balloon
    with a big white "$" tied to a stack of cases. Three hard strokes; with each one the tag swells. A notice behind
    says CARD FEES ADD 2-3% TO ALL PRICES. On the last stroke he turns his head to us, wry."""
    where = place("stockroom")
    DX = -0.30
    data = load_data(); data.place(DX, 0.0, 90)
    PUMP = Vector((DX + 0.105, 0.0, 0.0))
    pump, handle, needle = XK.stirrup_pump("floor pump", tuple(PUMP), h=0.3, yaw=math.radians(90))
    H0 = handle.location.copy()
    cases = K.box("case stack", (0.2, 0.06, 0.12), (0.26, 0.2, 0.24), K.mat("case blue", "#2D6FB0", rough=0.75), bev=0.006)
    K.box("case stack top", (0.2, 0.06, 0.26), (0.22, 0.18, 0.04), K.mat("case orange", "#E07B2E", rough=0.75), bev=0.004)
    BAL = Vector((0.22, 0.04, 0.28))
    bal, _v = XK.price_balloon("price balloon", tuple(BAL), s=1.0)
    hose = XK._curve_tube("pump hose", [PUMP + Vector((0.0, -0.035, 0.03)), Vector((-0.02, -0.07, 0.01)), Vector((0.12, -0.05, 0.05)),
                                        BAL + Vector((0, -0.01, 0.0))], 0.007, XK._mat("pump black", "#1A1A1D", rough=0.5))
    STROKES = [0.6, 1.65, 2.7]
    PERIOD = 1.0
    DOWN, DWELL, UPS = PERIOD / 2, 0.0, PERIOD / 2
    TRAVEL = 0.08
    def stroke(t):
        d = 0.0
        for ts in STROKES:
            if ts <= t < ts + PERIOD: d = 0.5 - 0.5 * math.cos(2 * math.pi * (t - ts) / PERIOD)
        return d
    SCALES = [1.0, 1.35, 1.7, 2.05]
    def swell(t):
        s = SCALES[0]
        for k, ts in enumerate(STROKES):
            if t >= ts: s = SCALES[k] + (SCALES[k + 1] - SCALES[k]) * ease(min(1.0, (t - ts) / DOWN))
        return s
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        key_all(handle, f, loc=H0 - Vector((0, 0, TRAVEL * stroke(t))))
        s = swell(t); key_all(bal, f, scale=(s, s, s))
        key_all(needle, f, rot=(0, math.radians(-60 + 120 * (s - 1.0) / 1.05), 0))
    # the grip ends, in the world: the pump is turned 90 deg so its T-bar runs along Y (one end per hand, side-on)
    def grip(sy):
        return lambda t: PUMP + Vector((0, sy * 0.075, 0.012 + 0.3 * 0.8 + 0.18 - TRAVEL * stroke(t)))
    # facing +X the rig's L side is toward the lens (-Y): L takes the near end of the bar, R the far end
    data.reach("L", grip(-1), 0.0, DUR, back=None, elbow_out=0.35)
    data.reach("R", grip(1), 0.0, DUR, back=None, elbow_out=0.35)
    data.look_at(US, 0.0, max_yaw=40, blend=0.0)
    data.look_at(BAL + Vector((0, 0, 0.1)), 0.3, max_yaw=40, max_pitch=20)
    data.look_at(US, STROKES[-1] + 0.6, max_yaw=40)
    data.idle(0.0, DUR)
    data.expression("determined", 0.2, STROKES[-1] + 0.5)
    data.expression("wry", STROKES[-1] + 0.6, DUR + 1.0, blend=0.25)
    data.blink(1.3)
    data.finish()
    soft_key("pump key", (-0.6, -1.1, 1.0), (DX + 0.1, 0.0, 0.4), energy=30, size=36)
    soft_key("tag key", (0.6, -0.9, 0.9), (BAL.x, BAL.y, BAL.z + 0.1), energy=16, size=26)
    camera(Vector((-0.04, -1.25, 0.46)), Vector((-0.04, 0.2, 0.44)), Vector((-0.02, -1.18, 0.46)), Vector((-0.02, 0.2, 0.45)),
           DUR, (-0.04, 0.0, 0.42), lens=30, fstop=6.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("each pump stroke swells the red price tag", lambda: meshes([bal]), STROKES[0], DUR, {"hero": True, "moves": lambda: meshes([bal])}),
                        ("the pump handle goes down and up", lambda: meshes([handle]), STROKES[0], STROKES[-1] + DOWN + DWELL + UPS, {"moves": lambda: meshes([handle])})])


# ================================================================ SHOT 3: $149 a year
def shot3():
    """HE SHOVELS HIS FAMILY'S COIN HEAP INTO THE CARD USERS' POINTS SACK. From HIGH above in the kitchen at night:
    a heap of gold coins on the lino with a little "$149 A YEAR" flag in it, Data with a long coal shovel, and a fat
    burlap sack stencilled POINTS. Three scoops: dig, swing, and the coins arc off the blade into the sack. The heap
    shrinks, the sack bulges. He looks up at us, sad."""
    where = place("kitchen")
    data = load_data(); data.place(0.0, 0.16, 0)
    HEAP = Vector((-0.2, -0.2, 0.0))
    heap = XK.coin_heap("coin heap", tuple(HEAP), r=0.16, h=0.12, n=150)
    flag = K.empty("heap flag", (0, 0, 0))                              # built about the origin (absolute spots), then placed
    K.cyl("flag stick", (0, 0, 0.17), 0.004, 0.34, K.mat("flag stick", "#E6DCC6", rough=0.6), bev=0, parent=flag)
    K.box("flag cloth", (0.1, 0, 0.28), (0.2, 0.005, 0.11), K.mat("flag cloth", "#F7F4EC", rough=0.6), bev=0.002, parent=flag)
    K.text("flag text", "$149", (0.1, -0.004, 0.292), 0.062, (math.pi / 2, 0, 0), K.mat("flag ink", "#2B5C2E", rough=0.5), extrude=0.0015, parent=flag)
    K.text("flag text 2", "A YEAR", (0.1, -0.004, 0.247), 0.026, (math.pi / 2, 0, 0), K.mat("flag ink", "#2B5C2E", rough=0.5), extrude=0.0008, parent=flag)
    flag.location = HEAP + Vector((-0.09, 0.02, 0.0))
    SACK = Vector((0.23, -0.17, 0.0))
    sack, mouth = XK.sack("points sack", tuple(SACK), r=0.13, h=0.27)
    MOUTH = SACK + mouth
    shov, grip_l, mid_l = XK.shovel("coal shovel", length=0.42)
    GL = grip_l.z
    SCOOPS = [0.5, 2.0, 3.5]
    DIG, LIFT, DUMP, BACK = 0.35, 0.45, 0.3, 0.4
    G_DIG = Vector((-0.01, 0.06, 0.42)); G_DUMP = Vector((0.0, 0.06, 0.43))      # the D-grip, by his chest (his reach is 0.19 m)
    U_DIG = (G_DIG - (HEAP + Vector((0.04, 0.06, 0.03)))).normalized()
    U_DUMP = (G_DUMP - (MOUTH + Vector((-0.04, 0.0, 0.07)))).normalized()
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
    data.reach(R, lambda t: pose(t)[0], 0.0, DUR, back=None, elbow_out=0.4)
    data.reach(L, lambda t: pose(t)[0] - pose(t)[1] * 0.045, 0.0, DUR, back=None, elbow_out=0.4)
    # a load of coins rides the blade from the dig to the dump, then flies into the sack
    gold = bpy.data.materials.get("coins")
    load = K.empty("blade load", (0, 0, 0)); load.parent = shov
    K.sph("blade load heap", (0, -0.012, 0.0), 1.0, gold, scale=(0.035, 0.014, 0.04), parent=load)
    flyers = []
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        on = any(ts + DIG * 0.7 <= t < ts + DIG + LIFT + DUMP * 0.4 for ts in SCOOPS)
        load.scale = (1, 1, 1) if on else (0, 0, 0); load.keyframe_insert("scale", frame=f)
    proto = K.cyl("sack coin", (0, 0, -5), 0.018, 0.004, gold, v=20, bev=0.001)
    rnd = random.Random(3)
    for k, ts in enumerate(SCOOPS):
        a = ts + DIG + LIFT
        for j in range(9):
            o = proto.copy(); bpy.context.collection.objects.link(o); flyers.append(o)
            t0 = a + 0.05 + 0.02 * j; fl = 0.35
            for f in range(1, NF + 1):
                t = (f - 1) / FPS
                u = (t - t0) / fl
                src = pose(a + 0.05)[2]
                dst = MOUTH + Vector((math.cos(j * 2.1) * 0.03, math.sin(j * 2.1) * 0.02, -0.03))
                if u < 0: o.scale = (0, 0, 0); o.location = src
                elif u <= 1: o.scale = (1, 1, 1); o.location = src.lerp(dst, u) + Vector((0, 0, 0.1 * 4 * u * (1 - u))); o.rotation_euler = (8 * u, 5 * u, j)
                else: o.scale = (0, 0, 0); o.location = dst
                o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f); o.keyframe_insert("scale", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; n = sum(1 for ts in SCOOPS if t >= ts + DIG * 0.7)
        h = 1.0 - 0.28 * n
        prev = 1.0 - 0.28 * max(0, n - 1)
        if n and t < SCOOPS[n - 1] + DIG: h = prev + (h - prev) * ease((t - SCOOPS[n - 1] - DIG * 0.7) / (DIG * 0.3))
        heap.scale = (0.8 + 0.2 * h, 0.8 + 0.2 * h, h); heap.keyframe_insert("scale", frame=f)
        m = sum(1 for ts in SCOOPS if t >= ts + DIG + LIFT + 0.25)
        b = 1.0 + 0.2 * m
        pb_ = 1.0 + 0.2 * max(0, m - 1)
        if m and t < SCOOPS[m - 1] + DIG + LIFT + 0.55: b = pb_ + (b - pb_) * ease((t - SCOOPS[m - 1] - DIG - LIFT - 0.25) / 0.3)
        sack.scale = (b, b, 1.0 + 0.12 * (b - 1.0) / 0.2); sack.keyframe_insert("scale", frame=f)
        flag.location = HEAP + Vector((-0.09, 0.02, 0.12 * (h - 1.0))); flag.keyframe_insert("location", frame=f)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(HEAP, 0.3, max_yaw=30, max_pitch=40)
    data.look_at(MOUTH, SCOOPS[0] + DIG + 0.1, max_yaw=30, max_pitch=40)
    data.look_at(HEAP, SCOOPS[1], max_yaw=30, max_pitch=40)
    data.look_at(MOUTH, SCOOPS[1] + DIG + 0.1, max_yaw=30, max_pitch=40)
    data.look_at(Vector((0.02, -0.77, 0.9)), DUR - 1.1, max_yaw=20, max_pitch=40)
    data.idle(0.0, DUR)
    data.expression("determined", 0.2, DUR - 1.2)
    data.expression("sad", DUR - 1.1, DUR + 1.0, blend=0.25)
    data.blink(1.1)
    data.finish()
    camera(Vector((0.02, -0.82, 0.92)), Vector((0.01, -0.04, 0.36)), Vector((0.02, -0.77, 0.9)), Vector((0.01, -0.04, 0.36)),
           DUR, (0.0, -0.1, 0.25), lens=26, fstop=6.0)
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
    DX, DY = -0.33, -0.02
    data = load_data(); data.place(DX, DY, 20)
    L, R = sides(data)
    HUB = Vector((DX + 0.16, DY + 0.04, 0.42))
    A = Vector((-0.06, -0.04, 0.08)); B = Vector((0.3, 0.02, 0.8))
    belt, wheel, cleats, belt_fn, WR = XK.conveyor("money conveyor", A, B, w=0.11, cleats=12, hub=HUB, WR=0.075)
    BK = Vector((A.x - 0.085, A.y - 0.05, 0.0))
    bucket = XK.tin_bucket("tin bucket", tuple(BK), r=0.075, h=0.085)
    K.text("bucket tag", "POOREST", (BK.x, BK.y - 0.075, 0.045), 0.024, (math.pi / 2, 0, 0), K.mat("tag ink dark", "#2B2B2E", rough=0.5), extrude=0.001)
    bfill = K.cyl("bucket coins", (BK.x, BK.y, 0.05), 0.064, 0.01, bpy.data.materials.get("coins") or K.mat("coins", "#F4CC52", rough=0.22, metal=0.65, emit=0.12), v=32, bev=0.002)
    PL = Vector((B.x + 0.07, B.y + 0.03, 0.0))
    K.box("vault plinth", (PL.x, PL.y, 0.22), (0.26, 0.22, 0.44), K.mat("plinth marble", "#E9E3D8", rough=0.2), bev=0.006)
    vault, fill, vm = XK.vault("vip vault", (PL.x, PL.y, 0.44), w=0.22, d=0.16, h=0.32, label="$750", sub="RICHEST")
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
    knob = lambda t: HUB + Vector((WR * 0.86 * math.cos(-ang(t)), -0.045, WR * 0.86 * math.sin(ang(t))))
    data.reach(R, knob, 0.0, DUR, back=None, elbow_out=0.15)
    SPEED = 0.7                                                         # belt travel per wheel turn, as a fraction of the belt
    pos = lambda t: ang(t) / (2 * math.pi) * SPEED
    for k, c in enumerate(cleats):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (k / len(cleats) + pos(t)) % 1.0
            c.location = belt_fn(u); c.keyframe_insert("location", frame=f)
    gold = bpy.data.materials.get("coins")
    proto = K.cyl("belt coin", (0, 0, -5), 0.03, 0.008, gold, v=24, bev=0.0015)
    N = 14
    starts = [0.02 + 0.13 * i for i in range(N)]                       # belt position at which coin i boards
    coins = []
    for i, s0 in enumerate(starts):
        o = proto.copy(); bpy.context.collection.objects.link(o); coins.append(o)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = pos(t) - s0
            if u < 0: o.scale = (0, 0, 0); o.location = belt_fn(0.0)
            elif u < 1.0: o.scale = (1, 1, 1); o.location = belt_fn(u) + Vector((0, 0, 0.012)); o.rotation_euler = (0, -math.atan2(B.z - A.z, B.x - A.x), 0)
            else:
                d = min(1.0, (u - 1.0) / 0.12); o.scale = (1 - d, 1 - d, 1 - d) if d < 1 else (0, 0, 0)
                o.location = B + Vector((0.04 * d, 0.03 * d, -0.12 * d * d))
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f); o.keyframe_insert("scale", frame=f)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; done = sum(1 for s0 in starts if pos(t) - s0 >= 1.05)
        fill.scale = (1, 1, 0.04 + 0.9 * done / N); fill.keyframe_insert("scale", frame=f)
        left = sum(1 for s0 in starts if pos(t) - s0 < 0)
        bfill.location.z = 0.012 + 0.045 * left / N; bfill.keyframe_insert("location", frame=f)
    data.look_at(US, 0.0, max_yaw=25, blend=0.0)
    data.look_at(HUB, 0.25, max_yaw=30, max_pitch=25)
    data.look_at(B, 1.3, max_yaw=40, max_pitch=40)
    data.look_at(US, T1 - 0.2, max_yaw=25)
    data.idle(0.0, DUR)
    data.expression("determined", 0.2, T1 - 0.3)
    data.expression("wry", T1 - 0.2, DUR + 1.0, blend=0.25)
    data.blink(2.4)
    data.finish()
    soft_key("bank key", (-0.7, -1.4, 1.4), (0.0, -0.02, 0.45), energy=40, size=40)
    soft_key("vault key", (0.8, -1.0, 1.2), (PL.x, PL.y, 0.6), energy=16, size=22)
    camera(Vector((-0.03, -1.46, 0.6)), Vector((-0.03, 0.1, 0.48)), Vector((-0.03, -1.38, 0.6)), Vector((-0.03, 0.1, 0.48)),
           DUR, (0.0, -0.02, 0.45), lens=30, fstop=8.0)
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
    data = load_data(); data.place(0.0, 0.1, 0)
    L, R = sides(data)
    post = XK.signpost("crossroads sign", (0.25, 0.45, 0.0), h=0.92)
    coin = XK.flip_coin("giant coin", r=0.1, h=0.02)
    C0 = Vector((0.07, -0.06, 0.42))
    T_TOSS, T_CATCH = 0.9, 2.5
    PEAK = 0.96
    def cpos(t):
        if t < T_TOSS - 0.3: return C0
        if t < T_TOSS: return C0 + Vector((0, 0, 0.055 * math.sin(math.pi * (t - T_TOSS + 0.3) / 1.3) ** 2))
        if t < T_CATCH:
            u = (t - T_TOSS) / (T_CATCH - T_TOSS); z0 = 0.055 * math.sin(math.pi * 0.3 / 1.3) ** 2   # leaves his hands mid-throw
            return C0 + Vector((0.02 * u, 0, z0 * (1 - u) + (PEAK - C0.z) * 4 * u * (1 - u)))
        return C0 + Vector((0.02, 0, 0))
    def crot(t):
        if t < T_TOSS: return (0, 0, 0)
        if t < T_CATCH: return (2 * math.pi * 3.5 * (t - T_TOSS) / (T_CATCH - T_TOSS), 0, 0)
        return (0, 0, 2 * math.pi * 0.5 * (t - T_CATCH))                    # caught on its edge, turning: CASH ... CARD ... CASH
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
    data.look_at(C0, 0.3, max_yaw=20, max_pitch=25)
    data.look_at(C0 + Vector((0, 0, 0.5)), T_TOSS + 0.25, max_yaw=20, max_pitch=40)
    data.look_at(C0, T_CATCH - 0.15, max_yaw=20, max_pitch=25)
    data.look_at(US, T_CATCH + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TOSS)
    data.expression("surprised", T_TOSS + 0.1, T_CATCH, blend=0.15)
    data.expression("wry", T_CATCH + 0.5, DUR + 1.0, blend=0.25)
    data.blink(0.5)
    data.finish()
    camera(Vector((0.02, -0.62, 0.58)), Vector((0.03, 0.1, 0.62)), Vector((0.02, -0.58, 0.58)), Vector((0.03, 0.1, 0.62)),
           DUR, (0.05, -0.05, 0.5), lens=28, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("the giant CASH / CARD coin spins up and lands on its edge in his hands", lambda: meshes([coin]), T_TOSS, DUR,
                         {"hero": True, "moves": lambda: meshes([coin])})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
