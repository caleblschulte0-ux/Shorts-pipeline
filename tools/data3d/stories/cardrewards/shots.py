"""THE CARD REWARDS SHORT (the sixth 3D short, 2026-11-18): every time you pay cash, you pay for someone else's credit
card rewards (Boston Fed, Schuh/Shy/Stavins 2010). Each beat its own place and its own idea (script.json), every beat
a counter close-up with the idea's prop big in front of Data (data-3d-tabletop-beats). Every touched prop sits within
his 0.18 m reach and below his shoulders (the vanilla stills, 11-18: hands at shoulder height put his forearms in his
head).

  1 hook      store         coins pour out of his hand and pile up under a giant gold credit card
  2 the fee   warehouse     he taps the card reader and every price tag on the boxes shoots up
  3 $149      sorting_room  he tips his piggy bank and its coins pour out onto a gold card
  4 uphill    bank          he pulls a lever and coins climb a ramp from a tiny shack to a mansion
  5 payoff    store         he lays a gold card on a scale and it outweighs a whole stack of cash

Run through the shot harness (store/shots.py, STORY=cardrewards). The props are store/card_kit.py."""
import card_kit as CK
import saffron_kit as SK
import locations as LOC
import props
from mathutils import Euler

US = Vector((0.0, -1.3, 0.62))
RED = "#D93A2B"


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


def follow(obj, fn, t0=0.0, t1=None, rot_fn=None):
    for f in range(F(t0), F(t1 if t1 is not None else DUR) + 1):
        t = (f - 1) / FPS; obj.location = fn(t); obj.keyframe_insert("location", frame=f)
        if rot_fn: obj.rotation_euler = rot_fn(t); obj.keyframe_insert("rotation_euler", frame=f)


def reach(data, side, fn, t0, t1, lead=0.4, back=0.45, elbow_out=0.45):
    return data.reach(side, fn, t0, t1, lead=lead, back=back, elbow_out=elbow_out)


def sides(data):
    """(image-left hand, image-right hand) for a camera on -Y looking +Y"""
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


def heap(center, r, top_fn):
    """a coin heap's height over (x, y): a cone of radius r whose peak is top_fn(t) above its floor"""
    def h(x, y, t):
        d = math.hypot(x - center.x, y - center.y)
        return top_fn(t) * max(0.0, 1.0 - d / r) if d < r else None
    return h


def schedule(n, t0, t1, seed=1):
    rnd = random.Random(seed)
    return [t0 + (t1 - t0) * (i / max(1, n - 1)) + rnd.uniform(-0.02, 0.02) for i in range(n)]


def counter(name, TOP, BACK=-0.01, DEP=0.38, w=0.9, store=True):
    if store:
        SK.table(name, (0.0, BACK - DEP / 2, 0.0), w=w, d=DEP, h=TOP)
    else:
        K.box(name, (0.0, BACK - DEP / 2, TOP / 2), (w, DEP, TOP), K.mat(name, "#2F3A36", rough=0.25), bev=0.006)


def camera(C0, L0, C1, L1, t_end, focus, lens=32, fstop=5.0):
    cam = K.camera(tuple(C0), tuple(L0), lens=lens, fstop=fstop)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / t_end))), L0.lerp(L1, ease(min(1.0, t / t_end))), Vector(focus)))
    return cam


# ================================================================ SHOT 1: the hook
def shot1():
    """COINS LEAP OUT OF HIS WALLET AND PILE UP UNDER A GIANT GOLD CREDIT CARD. Close at the checkout counter: his open
    brown wallet lies at one end, a big gold rewards card stands upright at the other with a dark tray at its foot.
    From the first second, coin after coin hops out of the wallet in an arc across the counter and lands in the tray
    under the card; the heap grows. Data looks from the wallet to us, annoyed.
    (Rounds 1-3, 52/45/52: a mitten never read as a hand pouring, a cup, or a hand at all. The 180: no hand in it --
    his money visibly leaves HIS wallet and goes to the card on its own, which is exactly what the line says.)"""
    where = store_set()
    TOP = 0.36
    counter("checkout counter", TOP)
    data = load_data(); data.place(0.0, 0.08, 0)
    L, R = sides(data)
    CARD = Vector((-0.07, -0.05, TOP))
    CK.card_stand("card stand", tuple(CARD), w=0.13)
    crd = CK.card("hook card", (CARD.x, CARD.y - 0.006, TOP + 0.004), w=0.17, h=0.106, upright=True)
    DISH = Vector((-0.07, -0.125, TOP))
    dsh = CK.dish("coin tray", tuple(DISH), r=0.065)
    W = Vector((0.11, -0.13, TOP))
    wal = CK.wallet("wallet", tuple(W))
    T0, T1 = 0.3, DUR * 0.8
    N = 40
    cs = CK.coins(N, "hook coin", r=0.022, h=0.006)
    sched = schedule(N, T0, T1)
    top = lambda t: 0.012 + 0.05 * min(1.0, max(0.0, (t - T0) / (T1 - T0)))
    hh = heap(DISH, 0.06, top)
    def land(x, y, t):
        v = hh(x, y, t)
        if v is not None: return TOP + 0.008 + v
        if -0.45 < x < 0.45 and -0.39 < y < -0.01: return TOP + 0.002
        return None
    props.pour(cs, NF, sched, lambda t: W + Vector((-0.01, 0.0, 0.03)), land, kick_fn=lambda t: Vector((-0.62, 0.0, 0.95)), seed=3)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(W, 0.3, max_yaw=18, max_pitch=12)
    data.look_at(US, 1.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, DUR + 1.0)
    data.blink(2.6)
    data.finish()
    soft_key("counter key", (-0.5, -1.0, 1.1), (0.0, -0.1, TOP + 0.08), energy=22, size=34)
    soft_key("card key", (-0.5, -0.8, 0.9), (CARD.x, CARD.y, TOP + 0.07), energy=10, size=18)
    camera(Vector((0.0, -0.68, 0.5)), Vector((0.0, -0.05, 0.57)), Vector((0.0, -0.63, 0.5)), Vector((0.0, -0.05, 0.57)),
           T1, (0.0, -0.12, 0.42), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("coins hop out of his wallet and heap up under the gold card", lambda: meshes(cs) + meshes([dsh, crd, wal]), T0 + 0.3, DUR)])


# ================================================================ SHOT 2: the swipe fee
def shot2():
    """HE TAPS THE CARD READER AND EVERY PRICE TAG ON THE BOXES SHOOTS UP. A stockroom bench: three product boxes,
    each with a white price tag on a stick, and a card reader by his right hand. He taps the reader, its screen
    lights green, and one after another the tags shoot up on their sticks and go red."""
    where = place("warehouse")
    TOP = 0.34
    counter("stock bench", TOP)
    data = load_data(); data.place(0.0, 0.10, 0)
    L, R = sides(data)
    RD = Vector((0.075, -0.04, TOP))
    rd, lamp, keypt = CK.reader("card reader", tuple(RD))
    rd.scale = (1.5, 1.5, 1.5)
    KEY = RD + keypt * 1.5
    boxes = []; tags = []
    for i, (x, h, c, lab) in enumerate(((-0.205, 0.08, "#C8462E", "CEREAL"), (-0.135, 0.1, "#2D6FB0", "SOAP"), (-0.065, 0.07, "#E2B33C", "RICE"))):
        b = CK.product_box(f"product {i}", (x, -0.12, TOP), (0.062, 0.06, h), c, label=lab); boxes.append(b)
        tg, tm = CK.price_tag(f"price tag {i}", (x, -0.12, TOP + h - 0.02), stick=0.04); tags.append((tg, tm, TOP + h - 0.02))
    T_TAP = 1.0
    up = KEY + Vector((0, -0.005, 0.072)); on = KEY + Vector((0, -0.005, 0.06))
    hp = path([(0.0, up + Vector((0.01, 0.02, 0.0))), (T_TAP - 0.35, up), (T_TAP, on), (T_TAP + 0.3, up), (T_TAP + 1.2, up + Vector((0.01, 0.0, 0.0)))])
    reach(data, R, hp, 0.0, DUR, lead=0.7, back=0.7, elbow_out=0.4)
    CK.key_emission(lamp, [(0.0, 0.0), (T_TAP, 0.0), (T_TAP + 0.08, 18.0)], F)
    beep = bpy.data.lights.new("reader beep", 'POINT'); beep.color = (0.2, 1.0, 0.4); beep.shadow_soft_size = 0.02
    bo = bpy.data.objects.new("reader beep", beep); bpy.context.collection.objects.link(bo); bo.location = KEY + Vector((0, -0.04, 0.03))
    for t, e in ((0.0, 0.0), (T_TAP, 0.0), (T_TAP + 0.08, 6.0), (T_TAP + 0.9, 6.0), (T_TAP + 1.3, 1.5)):
        beep.energy = e; beep.keyframe_insert("energy", frame=max(1, F(t)))
    T_UP = [T_TAP + 0.35 + 0.3 * i for i in range(3)]
    for (tg, tm, z0), tu in zip(tags, T_UP):
        follow(tg, lambda t, tg=tg, z0=z0, tu=tu: Vector((tg.location.x, tg.location.y, z0 + 0.09 * (0 if t < tu else min(1.0, 1 - (1 - min(1.0, (t - tu) / 0.7)) ** 3)))), 0.0, DUR)
        tg.scale = (1.4, 1.4, 1.4)
        CK.key_color(tm, [(0.0, "#F7F4EC"), (tu, "#F7F4EC"), (tu + 0.5, RED)], F)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(KEY, 0.3, max_yaw=18, max_pitch=12)
    data.look_at(Vector((-0.16, -0.12, TOP + 0.2)), T_TAP + 0.3, max_yaw=18, max_pitch=12)
    data.look_at(US, T_UP[-1] + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TAP + 0.2)
    data.expression("wry", T_UP[-1] + 0.4, DUR + 1.0, blend=0.25)
    data.blink(0.6)
    data.finish()
    soft_key("bench key", (-0.55, -1.0, 1.1), (-0.1, -0.1, TOP + 0.1), energy=24, size=34)
    soft_key("tag key", (-0.3, -0.7, 0.9), (-0.16, -0.12, TOP + 0.25), energy=8, size=20)
    camera(Vector((-0.06, -0.7, 0.5)), Vector((-0.06, -0.05, 0.57)), Vector((-0.06, -0.65, 0.5)), Vector((-0.06, -0.05, 0.57)),
           T_UP[-1] + 0.4, (-0.08, -0.12, 0.45), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("every price tag shoots up and turns red", lambda: meshes([t[0] for t in tags]) + meshes(boxes), T_UP[0], DUR)])


# ================================================================ SHOT 3: $149 a year
def shot3():
    """HE TIPS HIS PIGGY BANK AND ITS COINS POUR OUT ONTO A GOLD CARD. At the kitchen table: a pink piggy bank on a
    little wooden block, a gold card lying flat in front of its snout. He puts his hand on the pig's back and tips it
    forward; coins pour out of it onto the card in a heap. He looks at us."""
    where = place("sorting_room")
    TOP = 0.28
    counter("kitchen table", TOP)
    data = load_data(); data.place(0.0, 0.10, 0)
    L, R = sides(data)
    S = 1.1
    YAW = -math.pi / 2                                    # snout to the camera: his hand tips it from behind
    PIV = Vector((-0.02, -0.095, TOP))
    pig, snout = CK.piggy("piggy bank", tuple(PIV), s=S, yaw=YAW)
    CARD = Vector((-0.02, -0.215, TOP))
    crd = CK.card("table card", tuple(CARD), w=0.17, h=0.107)
    T_ON, T_TIP, T_END = 0.6, 1.4, DUR * 0.75
    TILT = math.radians(40)
    tilt = lambda t: 0.0 if t < T_ON + 0.25 else TILT * ease(min(1.0, (t - T_ON - 0.25) / (T_TIP - T_ON - 0.25)))
    follow(pig, lambda t: PIV, 0.0, DUR, rot_fn=lambda t: Euler((0, tilt(t), YAW)))
    def world(local, a):
        """a point in the pig's own frame (x forward, z up) after tipping by a, in the world"""
        x, z = local.x, local.z
        fx, fz = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
        return PIV + Vector((fx * math.cos(YAW), fx * math.sin(YAW), fz))
    BACK = Vector((-0.085, 0, 0.14))                      # the top of the pig's rump, in its root frame
    on_back = lambda t: world(BACK, tilt(t)) + Vector((0, 0.01, 0.048))
    reach(data, L, on_back, 0.0, DUR, lead=0.6, back=0.6, elbow_out=0.4)
    mouth = lambda t: world(snout, TILT)
    N = 26
    cs = CK.coins(N, "pig coin", r=0.024, h=0.006)
    sched = schedule(N, T_TIP, T_END, seed=5)
    hh = heap(CARD + Vector((0, 0.02, 0)), 0.07, lambda t: 0.01 + 0.03 * min(1.0, max(0.0, (t - T_TIP) / (T_END - T_TIP))))
    def land(x, y, t):
        v = hh(x, y, t)
        if v is not None: return TOP + 0.004 + v
        if -0.45 < x < 0.45 and -0.39 < y < -0.01: return TOP + 0.002
        return None
    props.pour(cs, NF, sched, mouth, land, kick_fn=lambda t: Vector((0.0, -0.2, 0.0)), seed=9)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(PIV, 0.3, max_yaw=18, max_pitch=12)
    data.look_at(CARD, T_TIP, max_yaw=18, max_pitch=12)
    data.look_at(US, T_END - 0.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.4, T_END - 0.4)
    data.expression("wry", T_END - 0.3, DUR + 1.0, blend=0.25)
    data.blink(1.0)
    data.finish()
    soft_key("table key", (-0.55, -1.0, 1.0), (0.0, -0.08, TOP + 0.08), energy=22, size=32)
    soft_key("pig key", (0.45, -0.8, 0.8), (PIV.x, PIV.y, TOP + 0.08), energy=9, size=18)
    camera(Vector((0.0, -0.68, 0.46)), Vector((0.0, -0.05, 0.55)), Vector((0.0, -0.63, 0.46)), Vector((0.0, -0.05, 0.55)),
           T_END, (0.0, -0.15, 0.36), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("he tips the piggy bank forward", lambda: meshes([pig]), T_ON + 0.25, DUR),
                        ("coins pour out of the pig onto the gold card", lambda: meshes(cs) + meshes([crd]), T_TIP + 0.3, DUR)])


# ================================================================ SHOT 4: it flows uphill
def shot4():
    """HE PULLS A LEVER AND COINS CLIMB A RAMP FROM A TINY SHACK UP TO A MANSION. On a dark bank counter: a tin shack
    low at the front left, a steep chunky ramp running diagonally up across the frame to a tall marble plinth on the
    right, a white mansion on top of it. Data pulls a big brass lever toward himself, and fat coins climb the ramp one
    after another, against gravity, and stack up in front of the mansion. He looks at us, unimpressed.
    (Round 1, 40: a shallow gold stick of a ramp, a mansion in front of his coat, the lever off frame. The 180: the
    rise is the picture now, the lever is in his near hand, the mansion stands off his body.)"""
    where = place("bank")
    TOP = 0.36
    counter("bank counter", TOP, store=False)
    data = load_data(); data.place(0.0, 0.10, 0)
    L, R = sides(data)
    PL = Vector((0.115, -0.1, TOP)); PH = 0.13
    plinth = K.box("mansion plinth", (PL.x, PL.y, TOP + PH / 2), (0.11, 0.12, PH), K.mat("plinth marble", "#E9E3D8", rough=0.2), bev=0.004)
    K.box("plinth cap", (PL.x, PL.y, TOP + PH + 0.004), (0.12, 0.13, 0.008), CK._mat("plinth gold", "#C9A04A", rough=0.3, metal=0.9), bev=0.002)
    man = CK.mansion("mansion", (PL.x, PL.y + 0.02, TOP + PH + 0.008), s=0.62)
    shk = CK.shack("shack", (-0.135, -0.2, TOP), s=1.05)
    A = Vector((-0.085, -0.19, TOP + 0.01)); B = Vector((0.06, -0.135, TOP + PH + 0.006))
    ramp = CK.chute("ramp", A, B, w=0.07, color="#C98A3E")
    for k, u in enumerate((0.35, 0.7)):                    # legs under the ramp, so it is a built thing on the counter
        p = A.lerp(B, u); K.box(f"ramp leg {k}", (p.x, p.y, (TOP + p.z) / 2), (0.01, 0.01, p.z - TOP), CK._mat("chute tin", "#A9AEB3", rough=0.35, metal=0.8), bev=0.001)
    PILE = Vector((PL.x - 0.03, PL.y - 0.03, TOP + PH + 0.008))
    BTN = Vector((-0.125, -0.045, TOP))
    btn, dome = CK.button("big button", tuple(BTN), h=0.06)
    T_PULL0, T_PULL1 = 0.7, 1.0
    TOPB = BTN + Vector((0, 0, 0.06 + 0.022))
    hp = path([(0.0, TOPB + Vector((0.01, 0.005, 0.05))), (T_PULL0, TOPB + Vector((0, 0, 0.045))), (T_PULL1, TOPB + Vector((0, 0, 0.032))),
               (T_PULL1 + 0.4, TOPB + Vector((0, 0, 0.045))), (DUR, TOPB + Vector((0.01, 0.01, 0.05)))])
    reach(data, L, hp, 0.0, DUR, lead=0.7, back=0.7, elbow_out=0.4)
    for t, z in ((0.0, 1.0), (T_PULL1 - 0.1, 1.0), (T_PULL1, 0.45), (T_PULL1 + 0.35, 0.45), (T_PULL1 + 0.6, 1.0)):
        dome.scale = (1, 1, z); dome.keyframe_insert("scale", frame=max(1, F(t)))
    P0 = BTN
    N = 16
    T0, T1 = T_PULL1 + 0.05, DUR * 0.82
    sched = schedule(N, T0, T1 - 0.9, seed=4)
    RIDE = 0.9
    climbers = CK.coins(N, "climbing coin", r=0.024, h=0.007)
    for o, ts in zip(climbers, sched):
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - ts) / RIDE
            if 0 <= u <= 1:
                o.location = A.lerp(B, u) + Vector((0, 0, 0.026)); o.scale = (1, 1, 1)
                o.rotation_euler = (math.pi / 2, 0, math.atan2(B.y - A.y, B.x - A.x) + u * 0)   # on its edge, rolling up
            else:
                o.location = A if u < 0 else B; o.scale = (0, 0, 0)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f); o.keyframe_insert("rotation_euler", frame=f)
    pile = CK.coins(N, "pile coin", r=0.024, h=0.007)
    hh = heap(PILE, 0.055, lambda t: 0.015 + 0.05 * min(1.0, max(0.0, (t - T0 - RIDE) / (T1 - T0))))
    def land(x, y, t):
        v = hh(x, y, t)
        if v is not None: return TOP + PH + 0.008 + v
        if abs(x - PL.x) < 0.08 and abs(y - PL.y) < 0.065: return TOP + PH + 0.008
        if -0.45 < x < 0.45 and -0.39 < y < -0.01: return TOP + 0.002
        return None
    props.pour(pile, NF, [s + RIDE for s in sched], lambda t: B + Vector((0.012, 0.0, 0.02)), land,
               kick_fn=lambda t: Vector((0.12, 0.02, 0.05)), seed=6)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(BTN, 0.4, max_yaw=18, max_pitch=12)
    data.look_at(PILE, T0 + 0.5, max_yaw=18, max_pitch=12)
    data.look_at(US, T1 - 0.5, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T1 - 0.6)
    data.expression("wry", T1 - 0.5, DUR + 1.0, blend=0.25)
    data.blink(2.2)
    data.finish()
    soft_key("bank key", (-0.55, -1.0, 1.1), (0.0, -0.14, TOP + 0.08), energy=24, size=36)
    soft_key("mansion key", (0.6, -0.8, 0.9), (PL.x, PL.y, TOP + PH + 0.05), energy=10, size=18)
    soft_key("ramp key", (-0.3, -0.7, 0.7), (-0.05, -0.17, TOP + 0.06), energy=8, size=22)
    camera(Vector((-0.01, -0.72, 0.52)), Vector((-0.01, -0.05, 0.57)), Vector((-0.01, -0.67, 0.52)), Vector((-0.01, -0.05, 0.57)),
           T1, (0.0, -0.15, 0.44), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("coins climb the ramp from the shack up to the mansion", lambda: meshes(climbers) + meshes([shk, ramp]), T0 + 0.3, T1),
                        ("the pile grows in front of the mansion", lambda: meshes(pile) + meshes([man, plinth]), T0 + RIDE, DUR)])


# ================================================================ SHOT 5: the payoff
def shot5():
    """HE LAYS A GOLD CARD ON A SCALE AND IT OUTWEIGHS A WHOLE STACK OF CASH. Back at the checkout: a brass balance,
    a fat stack of cash weighing its left pan down. He lays one gold card on the right pan and the beam swings hard
    the other way, lifting the cash. He looks at us: cash or card?"""
    where = store_set()
    TOP = 0.3
    counter("checkout counter", TOP)
    data = load_data(); data.place(0.0, 0.10, 0)
    L, R = sides(data)
    BX, BY, ARM, H = -0.03, -0.05, 0.12, 0.25
    bal, beam, pans = SK.balance("scale", (BX, BY, TOP), arm=ARM, h=H, pan_r=0.058)
    steel = CK._mat("scale pan steel", "#D5D9DE", rough=0.25, metal=0.9)
    for o in bpy.data.objects:
        if o.name.startswith("scale pan "): o.data.materials.clear(); o.data.materials.append(steel)
    T_LAY = 1.5
    def tilt(t):
        if t < T_LAY: return math.radians(-15)
        u = (t - T_LAY) / 0.3
        if u < 1: return math.radians(-15 + 45 * ease(u))
        return math.radians(30 - 5 * math.sin(min(1.0, (u - 1) / 1.2) * math.pi) * math.exp(-(u - 1)))
    for f in range(1, NF + 1):
        beam.rotation_euler = (0, tilt((f - 1) / FPS), 0); beam.keyframe_insert("rotation_euler", frame=f)
    SK.level_pans(beam, pans, NF)
    panL = bpy.data.objects["scale pan -1"]; panR = bpy.data.objects["scale pan 1"]
    def pan_top(o, t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return o.matrix_world.translation + Vector((0, 0, 0.005))
    tops = {o.name: [pan_top(o, (f - 1) / FPS) for f in range(1, NF + 1)] for o in (panL, panR)}
    at = lambda o, t: tops[o.name][min(NF - 1, max(0, F(t) - 1))]
    stack = SK.cash_stack("cash on the scale", tuple(at(panL, 0.0)), n=34)
    follow(stack, lambda t: at(panL, t), 0.0, DUR)
    crd = CK.card("scale card", (0, 0, 0), w=0.14, h=0.088)
    START = at(panR, 0.0) + Vector((0.0, 0.01, 0.05))
    hand = path([(0.0, START), (T_LAY, at(panR, T_LAY) + Vector((0, 0, 0.026))),
                 (T_LAY + 0.45, at(panR, T_LAY + 0.45) + Vector((0, 0, 0.05))), (T_LAY + 1.4, at(panR, T_LAY) + Vector((0.06, 0.06, 0.02)))])
    follow(crd, lambda t: hand(t) - Vector((0, 0, 0.024)) if t < T_LAY else at(panR, t), 0.0, DUR)
    reach(data, R, hand, 0.0, DUR, lead=1.0, back=0.8, elbow_out=0.4)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(at(panR, T_LAY), 0.3, max_yaw=18, max_pitch=12)
    data.look_at(at(panL, T_LAY + 0.5), T_LAY + 0.3, max_yaw=18, max_pitch=12)
    data.look_at(US, T_LAY + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T_LAY + 0.4)
    data.expression("wry", T_LAY + 0.6, DUR + 1.0, blend=0.25)
    data.blink(0.8)
    data.finish()
    soft_key("counter key", (-0.55, -1.0, 1.1), (BX, BY, TOP + 0.12), energy=22, size=32)
    soft_key("scale key", (0.45, -0.8, 0.9), (BX, BY, TOP + 0.1), energy=9, size=20)
    camera(Vector((-0.02, -0.72, 0.52)), Vector((-0.02, -0.05, 0.57)), Vector((-0.02, -0.67, 0.52)), Vector((-0.02, -0.05, 0.57)),
           T_LAY + 0.8, (BX, BY, TOP + 0.14), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("the card drops its pan and lifts the cash", lambda: meshes([bal, stack, crd]), T_LAY + 0.2, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


