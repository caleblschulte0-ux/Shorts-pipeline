"""THE HELIUM SHORT (the fourth 3D short, 2026-11-15): the gas in party balloons is running out, and we can't make
more. Made end to end without a sign-off (caaleb, 2026-11-15: "start working on a new video and all the new fixes"),
each beat its own place and its own idea (script.json `sets`, `ideas`), every prop big and right in front of him.

  1 hook     store      his big bunch of balloons shrivels and sags in his hand
  2 the well gas_field  he turns a wellhead wheel and gas from the ground swells a balloon on the pipe
  3 escape   dock       he jumps for an escaping balloon and it gets away into the sky
  4 the job  hospital   he pours a smoking flask of freezing helium into a giant scanner
  5 payoff   store      he ties the last balloon down instead of letting it go

Run through the shot harness (store/shots.py, STORY=helium). The props are store/helium_kit.py."""
import helium_kit as HK
import saffron_kit as SK
import locations as LOC

TABLE = Vector((0.0, -0.32, 0.0))
TABLE_H = 0.32
US = Vector((0.0, -1.3, 0.62))
COLORS = ("#D22B2B", "#2F7FD8", "#F2C230", "#3FAF5A", "#E2559B", "#F07F2A")


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
    sc.frame_set(1); bpy.context.view_layer.update()
    l, r = sorted("LR", key=lambda s: acts._shoulder(data, s).x)
    return l, r


def path(keys):
    def fn(t):
        if t <= keys[0][0]: return Vector(keys[0][1])
        for (ta, a), (tb, b) in zip(keys, keys[1:]):
            if t <= tb: return Vector(a).lerp(Vector(b), ease((t - ta) / max(1e-6, tb - ta)))
        return Vector(keys[-1][1])
    return fn


def hand_at(data, side, t):
    """where his real hand is at t (after finish(): the props ride the solved hand, not the planned point)"""
    sc.frame_set(F(t)); bpy.context.view_layer.update()
    pb = data.pb[f"hand.{side}"]
    return data.arm.matrix_world @ pb.tail


def bob(t, seed=0, amp=0.012):
    return Vector((amp * 0.6 * math.sin(1.7 * t + seed), amp * 0.4 * math.sin(1.3 * t + 2 * seed), amp * math.sin(1.1 * t + seed * 0.7)))


# ================================================================ SHOT 1: the hook
def shot1():
    """HIS BIG BUNCH OF BALLOONS SHRIVELS AND SAGS. Close in the party aisle: Data holds a fat bunch of six shiny
    balloons on strings in front of him, the bunch filling the frame beside his face. One by one they go limp and
    drop until he holds a droop of wrinkled rubber hanging under his fist. He looks at us, alarmed."""
    where = store_set()
    data = load_data(); data.place(0.0, 0.08, 0)
    L, R = sides(data)
    sh = acts._shoulder(data, L)
    H = sh + Vector((-0.05, -0.17, 0.0))                       # his fist, in front of his chest on the image-left
    reach(data, L, lambda t: H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    # the bunch: knots fanned up and out to the image-left, clear of his face
    UP = [Vector(v) for v in ((-0.24, 0.0, 0.27), (-0.12, -0.04, 0.3), (-0.34, 0.03, 0.18), (-0.2, -0.08, 0.16),
                              (-0.36, -0.05, 0.31), (-0.09, -0.1, 0.19))]
    T_GO = [0.6 + 0.36 * i for i in range(6)]                  # one after another, the last just before the line ends
    balloons = []
    for i, (u, tg) in enumerate(zip(UP, T_GO)):
        b = HK.balloon(f"bunch balloon {i}", (0, 0, 0), r=0.085 + 0.01 * (i % 3), color=COLORS[i])
        HK.shrivel(b, tg, tg + 0.55, seed=i)
        down = Vector((-0.012 * i + 0.03, -0.01, -0.07 - 0.01 * i))  # once limp it hangs under his fist
        kp = lambda t, u=u, tg=tg, down=down, i=i: H + u.lerp(down, ease(min(1.0, max(0.0, (t - tg - 0.15) / 0.6)))) + bob(t, i) * (1 if t < tg else 0.3)
        follow(b, kp, 0.0, DUR)
        HK.string_between(f"bunch string {i}", lambda t: H, kp, NF)
        balloons.append(b)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(H + Vector((-0.12, 0, 0.3)), 0.7, max_yaw=35, max_pitch=30)
    data.look_at(H + Vector((-0.08, 0, 0.05)), T_GO[3], max_yaw=35, max_pitch=40)
    data.look_at(US, T_GO[5] + 0.35, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("happy", 0.0, T_GO[0] + 0.2)
    data.expression("worried", T_GO[1], T_GO[5])
    data.expression("alarmed", T_GO[5] + 0.4, DUR + 1.0, blend=0.15)
    data.blink(0.5)
    data.finish()
    soft_key("bunch key", (-0.7, -1.0, 1.1), tuple(H + Vector((-0.15, 0, 0.2))), energy=26, size=34)
    C0, L0 = Vector((-0.2, -1.05, 0.8)), Vector((-0.2, 0.0, 0.7))
    C1, L1 = Vector((-0.16, -0.95, 0.72)), Vector((-0.14, 0.0, 0.6))   # it follows the bunch down as it drops
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / DUR))), L0.lerp(L1, ease(min(1.0, t / DUR))), Vector((-0.1, -0.1, 0.6))))
    return dict(**where, data=data, rest=1, grips=("bunch",),
                conseq=[("the balloons shrivel and drop one by one", lambda: meshes(balloons), T_GO[0], DUR)])


# ================================================================ SHOT 2: the well
def shot2():
    """GAS FROM THE GROUND SWELLS A BALLOON ON THE PIPE. A red wellhead stands out of the bare plains right in front
    of Data, its big handwheel flat on top at his chest, a limp balloon tied over the open nozzle of its branch pipe
    to the image-left. He takes the wheel in both hands and turns it, and the balloon on the pipe fills out huge and
    round with gas from underground. He looks at us, pleased."""
    where = place("gas_field")
    data = load_data(); data.place(0.04, 0.12, 0)
    L, R = sides(data)
    WH = Vector((0.03, -0.12, 0.0))
    root, wheel, noz_l, wc_l, WR = HK.wellhead("wellhead", tuple(WH), h=0.24, arm=0.3, rise=0.24)
    NOZ = WH + noz_l; WC = WH + wc_l
    T_GRIP, T_TURN0, T_TURN1 = 0.5, 0.9, DUR - 1.4
    turns = 1.6                                                  # full turns of the wheel
    spin = lambda t: -math.tau * turns * ease(min(1.0, max(0.0, (t - T_TURN0) / (T_TURN1 - T_TURN0))))
    follow(wheel, lambda t: wc_l, 0.0, DUR, rot_fn=lambda t: (0, 0, spin(t)))     # in the wellhead's own space
    b = HK.balloon("well balloon", tuple(NOZ), r=0.15, color="#2F7FD8")
    HK.inflate(b, T_TURN0 + 0.2, T_TURN1, frm=0.22)
    # his hands ride the rim, a quarter turn at a time: each hand slides back to its side while the other holds
    def rim(side, t):
        base = math.pi if side == L else 0.0                     # image-left hand on the -X rim, image-right on +X
        a = base + 0.35 * math.sin(spin(t) * 2.0) * (1 if side == L else -1)
        return WC + Vector((math.cos(a) * WR, math.sin(a) * WR - 0.01, 0.02))
    for sd in (L, R):
        reach(data, sd, lambda t, sd=sd: rim(sd, t), T_GRIP, T_TURN1 + 0.2, lead=0.4, back=0.5, elbow_out=0.5)
    data.look_at(WC + Vector((0, 0, 0.02)), 0.0, max_yaw=30, max_pitch=40, blend=0.0)
    data.look_at(NOZ + Vector((0, 0, 0.15)), T_TURN0 + 1.2, max_yaw=40, max_pitch=30)
    data.look_at(US, T_TURN1 + 0.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T_TURN1 - 0.6)
    data.expression("happy", T_TURN1 + 0.2, DUR + 1.0, blend=0.3)
    data.blink(1.6)
    data.finish()
    soft_key("well key", (-0.8, -1.0, 1.0), tuple(NOZ + Vector((0, 0, 0.12))), energy=22, size=36)
    C0, L0 = Vector((-0.1, -1.05, 0.5)), Vector((-0.08, 0.0, 0.42))
    C1, L1 = Vector((-0.1, -0.98, 0.52)), Vector((-0.1, 0.0, 0.46))
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((-0.08, -0.1, 0.45))))
    return dict(**where, data=data, rest=1, grips=("wellhead",),
                conseq=[("the balloon on the pipe fills out huge", lambda: meshes([b]), T_TURN0, DUR)])


# ================================================================ SHOT 3: escape
def shot3():
    """HE JUMPS FOR AN ESCAPING BALLOON AND IT GETS AWAY. Low on the dock with open sky behind: Data holds a big red
    balloon up on its string; it slips out of his fist, rises past his face, he jumps with both arms up and misses
    the string by a hand, and it climbs away into the sky, shrinking to a dot. He lands and stares after it."""
    where = place("dock")
    data = load_data(); data.place(0.0, 0.1, 0)
    L, R = sides(data)
    shR = acts._shoulder(data, R)
    H0 = shR + Vector((0.05, -0.14, 0.04))
    T_SLIP, T_JUMP, T_LAND = 0.9, 1.45, 2.05
    # the balloon: on its string in his fist, then free and rising, faster as it goes, drifting off to the image-left
    rise = lambda u: Vector((-0.06 * u - 0.02 * u * u, 0.25 * u * u, 0.45 * u + 0.35 * u * u))
    KN0 = H0 + Vector((0.0, -0.02, 0.3))
    kp = lambda t: (KN0 + bob(t, 3)) if t < T_SLIP else KN0 + rise(t - T_SLIP) + bob(t, 3) * 0.5
    b = HK.balloon("escape balloon", tuple(KN0), r=0.12, color="#D22B2B")
    follow(b, kp, 0.0, DUR)
    tail = lambda t: (H0 if t < T_SLIP else kp(t) + Vector((0.01, 0, -0.32)))
    HK.string_between("escape string", tail, kp, NF)
    reach(data, R, lambda t: H0, 0.0, T_SLIP + 0.05, lead=0.05, back=None, elbow_out=0.4)
    # the jump: the whole body up and down (anticipation crouch, launch, hang, land, settle)
    arm = data.arm; z0 = arm.location.z
    for t, z in ((0.0, 0), (T_JUMP - 0.22, 0), (T_JUMP - 0.08, -0.03), (T_JUMP + 0.15, 0.13), (T_JUMP + 0.32, 0.15),
                 (T_LAND - 0.05, 0.02), (T_LAND, -0.02), (T_LAND + 0.18, 0.0), (DUR, 0.0)):
        arm.location.z = z0 + z; arm.keyframe_insert("location", frame=F(t), index=2)
    def up(side, t):           # both arms reach straight up for the string, the image-right a hand short of it
        s = acts._shoulder(data, side)
        return s + Vector((0.11 if side == R else -0.11, -0.1, 0.14))
    for sd in (L, R):
        reach(data, sd, lambda t, sd=sd: up(sd, t), T_JUMP - 0.05, T_LAND, lead=0.25, back=0.5, elbow_out=0.25)
    data.look_at(KN0 + Vector((0, 0, 0.1)), 0.0, max_yaw=25, max_pitch=40, blend=0.0)
    data.look_at(kp(T_JUMP + 0.3), T_JUMP, max_yaw=30, max_pitch=55)
    data.look_at(kp(DUR - 0.3), T_LAND + 0.4, max_yaw=30, max_pitch=60)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_SLIP)
    data.expression("surprised", T_SLIP + 0.12, T_LAND, blend=0.12)
    data.expression("sad", T_LAND + 0.3, DUR + 1.0, blend=0.3)
    data.blink(0.6)
    data.finish()
    soft_key("balloon key", (0.6, -1.0, 0.9), tuple(KN0 + Vector((0, 0, 0.1))), energy=20, size=40)
    C0, L0 = Vector((0.06, -1.15, 0.3)), Vector((0.02, 0.2, 0.75))   # low, looking up: the sky behind the climb
    C1, L1 = Vector((0.06, -1.15, 0.3)), Vector((-0.06, 0.4, 1.05))  # tilts up after it as it climbs away
    cam = K.camera(tuple(C0), tuple(L0), lens=28, fstop=5.6)
    camera_path(cam, lambda t: (C0, L0.lerp(L1, ease(min(1.0, max(0.0, (t - T_SLIP) / (DUR - T_SLIP))))), Vector((0.0, 0.1, 0.6))))
    return dict(**where, data=data, rest=1, grips=("escape",),
                conseq=[("the balloon rises out of reach and away into the sky", lambda: meshes([b]), T_SLIP, T_SLIP + 1.1, {"whole": False})])


# ================================================================ SHOT 4: the scanner
def shot4():
    """HE POURS A SMOKING FLASK OF FREEZING HELIUM INTO A GIANT SCANNER. A huge white hospital scanner fills the room
    behind; its fill line comes down to a steel funnel on a low cart right in front of Data. He tips a big silver
    flask over the funnel and white freezing smoke pours out, rolling and sinking; frost creeps over the line and the
    scanner's big status light goes from red to green. He looks at us, impressed."""
    where = place("hospital")
    data = load_data(); data.place(-0.2, 0.12, 0)
    L, R = sides(data)
    scan, stat, port_l = HK.scanner("scanner", (0.42, 0.75, 0), R=0.5, depth=0.5)
    CART = Vector((0.0, -0.18, 0.0)); CH = 0.3
    steel = HK._mat("cart steel", "#B5BABF", rough=0.3, metal=1.0)
    K.box("cart top", tuple(CART + Vector((0, 0, CH))), (0.5, 0.26, 0.025), steel, bev=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1): K.cyl("cart leg", tuple(CART + Vector((sx * 0.22, sy * 0.11, CH / 2))), 0.008, CH, steel, v=10, bev=0.001)
    FUN = CART + Vector((0.16, 0.0, CH + 0.02))
    K.cyl("funnel neck", tuple(FUN + Vector((0, 0, 0.03))), 0.012, 0.06, steel, v=16, bev=0.002)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.016, radius2=0.06, depth=0.07, location=tuple(FUN + Vector((0, 0, 0.095))))
    fun = bpy.context.active_object; fun.name = "funnel cone"; fun.data.materials.append(steel)
    hose = HK._mat("fill line", "#5E646B", rough=0.4, metal=0.6)
    P_HOSE = [FUN + Vector((0, 0.02, 0.03)), FUN + Vector((0.12, 0.25, 0.0)), Vector((0.3, 0.5, 0.35)), scan.location + Vector(port_l) + Vector((0, -0.05, -0.1))]
    segs = []
    for i, (a, c) in enumerate(zip(P_HOSE, P_HOSE[1:])):
        d = c - a; o = K.cyl(f"fill line {i}", tuple((a + c) / 2), 0.012, d.length, hose, v=12, bev=0.001)
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); segs.append(o)
    fl, mouth_l = HK.dewar("flask", (0, 0, 0), r=0.055, h=0.2)
    REST = CART + Vector((-0.03, -0.02, CH + 0.013))      # beside his chest, never in front of his face
    T_LIFT, T_TIP0, T_TIP1, T_DOWN = 0.5, 1.2, DUR - 1.8, DUR - 1.0
    OVER = FUN + Vector((-0.13, -0.04, 0.1))       # low and forward: never across his face
    fp = path([(0.0, REST), (T_LIFT, REST), (T_TIP0, OVER), (T_TIP1, OVER), (T_DOWN, REST)])
    tip = lambda t: 1.9 * ease(min(1.0, max(0.0, (t - T_TIP0 + 0.3) / 0.5))) * (1 - ease(min(1.0, max(0.0, (t - T_TIP1) / 0.5))))
    follow(fl, fp, 0.0, DUR, rot_fn=lambda t: (0, tip(t), 0))
    mouth = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), fl.matrix_world @ mouth_l)[2]
    puffs = HK.cold_smoke("cold", mouth, lambda t: Vector((0.6, 0.0, -0.4)), T_TIP0 + 0.2, T_TIP1 - 0.7, NF, n=70, seed=4)   # done before he tips it back
    HK.frost([o.name for o in segs] + ["funnel cone"], T_TIP0 + 0.4, T_TIP1)
    HK.status(stat, 0.0, "#E0302A"); HK.status(stat, T_TIP1 - 0.6, "#E0302A"); HK.status(stat, T_TIP1 - 0.3, "#2FD05A", emit=9.0)
    for sd, dx in ((L, -1), (R, 1)):
        reach(data, sd, lambda t, dx=dx: fp(t) + Vector((dx * 0.07, -0.01, 0.11)), T_LIFT - 0.1, T_DOWN + 0.05, lead=0.4, back=0.5, elbow_out=0.6)
    data.look_at(REST + Vector((0, 0, 0.12)), 0.0, max_yaw=30, max_pitch=40, blend=0.0)
    data.look_at(FUN + Vector((0, 0, 0.1)), T_TIP0, max_yaw=35, max_pitch=40)
    data.look_at(scan.location + Vector((0.3, -0.25, 0.65)), T_TIP1 - 0.35, max_yaw=45, max_pitch=30)
    data.look_at(US, T_DOWN + 0.2, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T_TIP1 - 0.4)
    data.expression("surprised", T_TIP1 - 0.25, T_DOWN, blend=0.12)
    data.expression("happy", T_DOWN + 0.2, DUR + 1.0, blend=0.3)
    data.blink(0.9)
    data.finish()
    soft_key("pour key", (-0.7, -1.0, 1.0), tuple(FUN + Vector((0, 0, 0.15))), energy=20, size=34)
    soft_key("scanner key", (0.9, -0.8, 1.4), tuple(scan.location + Vector((0, 0, 0.5))), energy=30, size=40, color=(0.92, 0.96, 1.0))
    C0, L0 = Vector((0.02, -1.15, 0.62)), Vector((0.08, 0.2, 0.5))
    C1, L1 = Vector((0.04, -1.1, 0.64)), Vector((0.12, 0.2, 0.55))
    cam = K.camera(tuple(C0), tuple(L0), lens=26, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((0.0, -0.1, 0.5))))
    return dict(**where, data=data, rest=1, grips=("flask", "funnel", "cart"),
                conseq=[("freezing smoke pours from the flask into the funnel", lambda: puffs, T_TIP0 + 0.3, T_TIP1, {"whole": False}),
                        ("the scanner's light goes from red to green", lambda: meshes([scan]), T_TIP1 - 0.6, DUR, {"whole": False})])


# ================================================================ SHOT 5: payoff
def shot5():
    """HE TIES THE LAST BALLOON DOWN INSTEAD OF LETTING IT GO. Close at the party aisle table: Data holds one big
    balloon up on its string and opens his fist to let it go, catches it, brings the string down and ties it round a
    heavy iron weight on the table in front of him. The balloon bobs, held down. He points at it and looks at us."""
    where = store_set()
    SK.table("party table", tuple(TABLE), w=0.9, d=0.42, h=TABLE_H)
    TOP = TABLE_H
    data = load_data(); data.place(0.0, 0.08, 0)
    L, R = sides(data)
    WT = Vector((-0.1, -0.36, TOP))
    w = HK.weight("weight", tuple(WT), s=0.13)
    TIE = WT + Vector((0, 0, w["tie"]))
    shL = acts._shoulder(data, L)
    UP = shL + Vector((-0.06, -0.16, 0.06))
    T_OPEN, T_CATCH, T_DOWN, T_TIE0, T_TIE1 = 0.6, 1.05, 1.8, 2.0, 2.9
    T_POINT = T_TIE1 + 0.35
    hp = path([(0.0, UP), (T_OPEN, UP + Vector((0, 0, 0.03))), (T_CATCH, UP + Vector((0, 0, 0.07))), (T_DOWN, TIE + Vector((0.0, -0.02, 0.05)))])
    def hand(t):
        if t < T_TIE0: return hp(t)
        u = (t - T_TIE0) / (T_TIE1 - T_TIE0)                     # two little loops round the weight's ring: tying it
        a = math.tau * 2 * ease(min(1.0, u))
        return TIE + Vector((0.035 * math.cos(a), -0.02 + 0.02 * math.sin(a), 0.05 - 0.02 * min(1.0, u)))
    reach(data, L, hand, 0.0, T_TIE1, lead=0.05, back=0.6, elbow_out=0.4)
    LEN = 0.27
    def knot(t):
        tail = hand(t) if t < T_TIE1 else TIE
        lift = 0.04 if T_OPEN < t < T_CATCH else 0.0             # it starts to float off when he opens his fist
        return tail + Vector((-0.02, 0.0, LEN + lift)) + bob(t, 5) * (0.6 if t < T_TIE1 else 1.4)
    b = HK.balloon("last balloon", tuple(knot(0.0)), r=0.12, color="#E2559B")
    follow(b, knot, 0.0, DUR)
    HK.string_between("last string", lambda t: hand(t) if t < T_TIE1 else TIE, knot, NF)
    # he points at it with his other hand: his arm straight out toward the balloon
    shR = acts._shoulder(data, R)
    reach(data, R, lambda t: shR + Vector((0.05, -0.17, -0.06)), T_POINT, DUR, lead=0.35, back=None, elbow_out=0.5)   # an open hand out to us: would you?
    data.look_at(knot(0.0), 0.0, max_yaw=30, max_pitch=40, blend=0.0)
    data.look_at(TIE + Vector((0, 0, 0.05)), T_DOWN - 0.3, max_yaw=30, max_pitch=45)
    data.look_at(US, T_POINT + 0.2, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_OPEN)
    data.expression("surprised", T_OPEN + 0.15, T_CATCH + 0.2, blend=0.18)
    data.expression("determined", T_DOWN, T_TIE1)
    data.expression("wry", T_POINT, DUR + 1.0, blend=0.3)
    data.blink(1.4)
    data.finish()
    soft_key("table key", (-0.6, -1.0, 1.0), tuple(TIE + Vector((0, 0, 0.2))), energy=24, size=36)
    C0, L0 = Vector((-0.08, -1.15, 0.66)), Vector((-0.06, -0.15, 0.6))
    C1, L1 = Vector((-0.06, -1.07, 0.64)), Vector((-0.06, -0.15, 0.57))
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=5.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((-0.06, -0.2, 0.55))))
    return dict(**where, data=data, rest=1, grips=("last", "weight"),
                conseq=[("the string is tied round the iron weight", lambda: meshes([w]), T_TIE0, DUR, {"whole": False}),
                        ("the balloon bobs, held down by the weight", lambda: meshes([b]), T_TIE1, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
