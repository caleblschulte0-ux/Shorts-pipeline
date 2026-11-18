"""THE CARD REWARDS SHORT (the sixth 3D short, 2026-11-18): every time you pay cash, you pay for someone else's credit
card rewards (Boston Fed, Schuh/Shy/Stavins 2010). Each beat its own place and its own idea (script.json), every beat
a counter close-up with the idea's prop big in front of Data (data-3d-tabletop-beats). Every touched prop sits within
his 0.18 m reach and below his shoulders (the vanilla stills, 11-18: hands at shoulder height put his forearms in his
head).

  1 hook      store         coins pour out of his hand and pile up under a giant gold credit card
  2 the fee   warehouse     he taps the card reader and every price tag on the boxes shoots up
  3 $149      sorting_room  he tips his piggy bank and its coins pour out onto a gold card
  4 uphill    bank          coins lob out of a poor family's cup and fill a rich family's jar
  5 payoff    store         his cash flies note by note into a gold card, and the card grows

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
    CARD = Vector((-0.09, -0.05, TOP))
    CK.card_stand("card stand", tuple(CARD), w=0.2)
    crd = CK.card("hook card", (CARD.x, CARD.y - 0.006, TOP + 0.004), w=0.27, h=0.17, upright=True)   # the beat's prop: a quarter of the frame
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
    """THE POOR FAMILY'S SHACK EMPTIES INTO THE RICH FAMILY'S JAR. On a dark bank counter: a tiny ribbed tin shack at
    the left, a tall white mansion at the right with a clear jar standing just left of it.
    Coin after coin lobs out of the shack's door, arcs UP across the counter and drops into the jar, which fills to the brim. Data
    watches them go, then looks at us, unimpressed.
    (2026-11-18 second rewrite, after a lever, a button and a ramp all scored 40-68: the judge never read the ramp or
    the button on a phone. One container empties into another; no hand in it. It is shot 1's coin arc, which passed.)"""
    where = place("bank")
    TOP = 0.36
    counter("bank counter", TOP, store=False)
    data = load_data(); data.place(0.0, 0.10, 0)
    shk = CK.shack("shack", (-0.13, -0.11, TOP), s=1.6)
    man = CK.mansion("mansion", (0.155, -0.04, TOP), s=1.35, wide=0.5)
    J = Vector((0.025, -0.165, TOP))
    jar, RIM, RIN = CK.coin_jar("rich jar", tuple(J), r=0.056, h=0.15)
    T0, T1 = 0.35, DUR * 0.85
    N = 40
    cs = CK.coins(N, "uphill coin", r=0.02, h=0.006)
    sched = schedule(N, T0, T1, seed=4)
    MOUTH = Vector((-0.13 + 0.07 * 1.6 * 0.15, -0.11 - 0.06 * 1.6 / 2 - 0.01, TOP + 0.03))   # out of the shack's door
    level = lambda t: 0.012 + (RIM - 0.035) * min(1.0, max(0.0, (t - T0) / (T1 - T0)))
    rnd = random.Random(9)
    spots = [(rnd.uniform(0, 6.28), RIN * 0.75 * math.sqrt(rnd.uniform(0, 1))) for _ in range(N)]
    CK.arc_into(cs, NF, FPS, sched, MOUTH, lambda i, t: J + Vector((math.cos(spots[i][0]) * spots[i][1], math.sin(spots[i][0]) * spots[i][1], level(t))),
                flight=0.65, apex=0.05)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(MOUTH, 0.3, max_yaw=18, max_pitch=12)
    data.look_at(J + Vector((0, 0, 0.1)), 1.4, max_yaw=18, max_pitch=12)
    data.look_at(US, T1 - 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T1 - 0.7)
    data.expression("neutral", T1 - 0.6, DUR + 1.0, blend=0.25)
    data.perform("wry", T1 - 0.55, hold=1.0, pace=0.7, arms=False)
    data.blink(2.2)
    data.finish()
    soft_key("bank key", (-0.55, -1.0, 1.1), (0.0, -0.14, TOP + 0.08), energy=24, size=36)
    soft_key("jar key", (0.6, -0.8, 0.9), (J.x, J.y, TOP + 0.1), energy=12, size=18)
    camera(Vector((0.0, -0.7, 0.52)), Vector((0.0, -0.05, 0.56)), Vector((0.0, -0.65, 0.52)), Vector((0.0, -0.05, 0.56)),
           T1, (0.02, -0.15, 0.45), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("coins arc out of the poor shack and fill the rich jar", lambda: meshes(cs) + meshes([jar]), T0 + 0.6, DUR, {"hero": True}),
                        ("the shack and the mansion both stay in view", lambda: meshes([shk, man]), 0.0, DUR)])


# ================================================================ SHOT 5: the payoff
def shot5():
    """HIS CASH FLIES NOTE BY NOTE INTO A GOLD CARD, AND THE CARD GROWS. Back at the checkout: a fat stack of cash at
    the left, a big gold rewards card standing upright at the right. One note after another lifts off the stack,
    arcs across and vanishes into the card; the stack shrinks and the card swells. He looks at us: cash or card?
    (2026-11-18 second rewrite, after a balance scale scored 56-66: a scale's tilt never read as "the card wins". A
    stack that shrinks and a card that grows needs no reading.)"""
    where = store_set()
    TOP = 0.36
    counter("checkout counter", TOP)
    data = load_data(); data.place(0.0, 0.08, 0)
    S = Vector((-0.1, -0.14, TOP))
    stack = SK.cash_stack("cash stack", tuple(S), n=60); stack.scale = (1.35, 1.35, 1.0)
    CARD = Vector((0.09, -0.06, TOP))
    CK.card_stand("card stand", tuple(CARD), w=0.19)
    crd = CK.card("fat card", (CARD.x, CARD.y - 0.006, TOP + 0.004), w=0.23, h=0.145, upright=True)
    T0, T1 = 0.4, DUR - 0.25
    N = 14
    bs = CK.bills(N, "flying note")
    sched = schedule(N, T0, T1 - 0.4, seed=5)
    H0 = 0.0012 * 60
    def stack_h(t): return 1.0 - 0.7 * min(1.0, max(0.0, (t - T0) / (T1 - T0)))
    def card_s(t): return 1.0 + 0.4 * min(1.0, max(0.0, (t - T0 - 0.4) / (T1 - T0)))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        stack.scale = (1.35, 1.35, stack_h(t)); stack.keyframe_insert("scale", frame=f)
        s_ = card_s(t); crd.scale = (s_, s_, s_); crd.keyframe_insert("scale", frame=f)
    INTO = CARD + Vector((0.0, -0.02, 0.07))
    for o, ts in zip(bs, sched):
        p0 = S + Vector((0, 0, H0 * stack_h(ts) + 0.005)); FL = 0.5
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - ts) / FL
            if 0 <= u <= 1:
                p = p0.lerp(INTO, u) + Vector((0, 0, 0.09 * math.sin(math.pi * u)))
                o.location = p; o.rotation_euler = (math.radians(70) * u, 0, math.radians(15) * math.sin(math.pi * u))
                k = 1.0 if u < 0.8 else max(0.0, (1 - u) / 0.2); o.scale = (k, k, k)
            else:
                o.location = p0; o.scale = (0, 0, 0)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_euler", frame=f); o.keyframe_insert("scale", frame=f)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(S, 0.3, max_yaw=18, max_pitch=12)
    data.look_at(CARD + Vector((0, 0, 0.08)), 1.3, max_yaw=18, max_pitch=12)
    data.look_at(US, 2.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, 2.5)
    data.expression("wry", 2.6, DUR + 1.0, blend=0.25)
    data.blink(1.0)
    data.finish()
    soft_key("counter key", (-0.5, -1.0, 1.1), (0.0, -0.1, TOP + 0.08), energy=22, size=34)
    soft_key("card key", (0.5, -0.8, 0.9), (CARD.x, CARD.y, TOP + 0.08), energy=10, size=18)
    camera(Vector((0.0, -0.68, 0.5)), Vector((0.0, -0.05, 0.57)), Vector((0.0, -0.63, 0.5)), Vector((0.0, -0.05, 0.57)),
           T1, (0.0, -0.12, 0.42), lens=24, fstop=4.0)
    return dict(**where, data=data, rest=1, grips=(),
                conseq=[("the cash stack shrinks note by note and the gold card swells", lambda: meshes([stack, crd]) + meshes(bs), T0 + 0.3, DUR,
                         {"hero": True, "moves": lambda: meshes([crd])})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


