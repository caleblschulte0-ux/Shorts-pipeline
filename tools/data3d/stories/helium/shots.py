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


def spline(keys):
    """a path THROUGH its keys without stopping at each (Catmull-Rom in time): path() eases every segment in and out,
    so each key is a dead stop, and a hand moved through three keys stutters twice (helium shot 5's slip and catch)"""
    ts = [k[0] for k in keys]; ps = [Vector(k[1]) for k in keys]; n = len(ps)
    def vel(i):
        if i == 0 or i == n - 1: return Vector((0, 0, 0))
        return (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1])
    def fn(t):
        if t <= ts[0]: return ps[0].copy()
        for i in range(n - 1):
            if t <= ts[i + 1]:
                h = ts[i + 1] - ts[i]; u = (t - ts[i]) / max(1e-6, h)
                h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
                return ps[i] * h00 + vel(i) * (h10 * h) + ps[i + 1] * h01 + vel(i + 1) * (h11 * h)
        return ps[-1].copy()
    return fn


def hand_at(data, side, t):
    """where his real hand is at t (after finish(): the props ride the solved hand, not the planned point)"""
    sc.frame_set(F(t)); bpy.context.view_layer.update()
    pb = data.pb[f"hand.{side}"]
    return data.arm.matrix_world @ pb.tail


def HK_fcurves(action):
    from character import _fcurves
    return _fcurves(action)


def bob(t, seed=0, amp=0.012):
    return Vector((amp * 0.6 * math.sin(1.7 * t + seed), amp * 0.4 * math.sin(1.3 * t + 2 * seed), amp * math.sin(1.1 * t + seed * 0.7)))


# ================================================================ SHOT 1: the hook
def shot1():
    """HIS BIG BUNCH OF BALLOONS SHRIVELS AND SAGS. Close in the party aisle: Data holds a fat bunch of six shiny
    balloons on strings up in front of him, the bunch filling the top of the frame beside his face. One by one each
    loses its gas where it floats: it goes soft and wrinkled, folds over its knot and sinks slowly down its own
    string to hang under his fist. He lifts the droop of limp rubber up to us, alarmed. (Round 1: 52, the
    balloons "shrank into jelly beans" and flew loose to a heap; round 2's helium tank was "the opposite of
    shriveling", 30. Round 3: 60, the limp ones swung down so fast they blurred into "balloons flying loose".)"""
    where = store_set()
    data = load_data(); data.place(0.02, 0.08, 0)
    L, R = sides(data)
    sh = acts._shoulder(data, L)
    H0 = sh + Vector((-0.08, -0.13, 0.02))                      # his fist up at his shoulder on the image-left: the
                                                                 # droop hangs at his chest, not his knees (round 1)
    H1 = sh + Vector((-0.07, -0.14, 0.03))                      # held up to show us what is left, out clear of his face
    T_GO = [0.2 + 0.26 * i for i in range(6)]
    T_UP0 = T_GO[-1] + 0.55; T_UP1 = T_UP0 + 0.6
    H = spline([(0.0, H0), (T_UP0, H0), (T_UP1, H1)])
    reach(data, L, H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    # the bunch: knots fanned up and out to the image-left, clear of his face
    UP = [Vector(v) for v in ((-0.12, 0.0, 0.3), (-0.07, -0.02, 0.36), (-0.21, 0.03, 0.24), (-0.13, -0.05, 0.2),
                              (-0.2, -0.02, 0.36), (-0.17, -0.07, 0.29))]   # a tight bunch over his fist, none over his face    # a wall over his head on the image-left    # up over his head to the image-left
    balloons = []
    for i, (u, tg) in enumerate(zip(UP, T_GO)):
        b = HK.balloon(f"bunch balloon {i}", (0, 0, 0), r=0.095 + 0.01 * (i % 3), color=COLORS[i])
        HK.shrivel(b, tg, tg + 0.45, to=0.62, seed=i, hang=True)       # it goes limp IN PLACE and folds over its knot
        Ls = 0.09 + 0.012 * i                                        # then falls on its string: a pendulum off his fist,
        dn = Vector((-0.02 + 0.008 * i, -0.04, -1.0)).normalized()   # never flying loose
        up = u.normalized()
        def kp(t, dn=dn, Ls=Ls, tg=tg, i=i, u=u):
            # it SINKS, slowly, down its own string to hang under his fist: no swing (a swing blurred into "flying
            # loose"), the knot sliding mostly straight down, drifting in under the fist only at the end
            k = ease(min(1.0, max(0.0, (t - tg - 0.25) / 1.0)))
            if k <= 0: return H(t) + u + bob(t, i) * (1.0 if t < tg else 0.4)
            end = dn * Ls
            mid = Vector((u.x * 0.8, u.y, (u.z + end.z) * 0.5))
            p = u * (1 - k) ** 2 + mid * 2 * k * (1 - k) + end * k * k
            return H(t) + p
        follow(b, kp, 0.0, DUR)
        HK.string_between(f"bunch string {i}", H, kp, NF)
        balloons.append(b)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(H0 + Vector((-0.12, 0, 0.3)), 0.35, max_yaw=18, max_pitch=22)   # the eyes go up: the head stays
    data.look_at(H0 + Vector((-0.08, 0, 0.0)), T_GO[3], max_yaw=18, max_pitch=30)   # open to us (round 3: back of his head)
    data.look_at(US, T_UP0 + 0.1, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("happy", 0.0, T_GO[0] + 0.15)
    data.expression("worried", T_GO[1], T_UP0)
    data.expression("alarmed", T_UP0 + 0.15, DUR + 1.0, blend=0.15)
    data.finish()
    soft_key("bunch key", (-0.7, -1.0, 1.1), tuple(H0 + Vector((-0.15, 0, 0.2))), energy=26, size=34)
    C0, L0 = Vector((-0.13, -1.12, 0.66)), Vector((-0.13, 0.0, 0.64))
    C1, L1 = Vector((-0.09, -0.98, 0.6)), Vector((-0.09, 0.0, 0.56))   # a push in to his face and the droop
    cam = K.camera(tuple(C0), tuple(L0), lens=28, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / DUR))), L0.lerp(L1, ease(min(1.0, t / DUR))), Vector((-0.06, -0.1, 0.6))))
    return dict(**where, data=data, rest=1, grips=("bunch",),
                conseq=[("the balloons shrivel and sag one by one", lambda: meshes(balloons), T_GO[0], DUR)])


# ================================================================ SHOT 2: the well
def shot2():
    """GAS FROM THE GROUND SWELLS A BALLOON ON THE WELLHEAD. Out on the gas plains a red wellhead stands at Data's
    right, an empty balloon flopped over the top of its tall riser. A big yellow valve wheel stands on the front of
    the pipe facing us, at his hip; he turns it the way you turn a stiff valve, his hand on the rim pushing it round
    a quarter turn, back for another grip, again and again, its spokes plainly turning, and the balloon up on the
    riser stands up and fills out huge and round with gas straight out of the ground. He looks at us, pleased.
    (Round 1: 58, a flat wheel "looked static". Round 2: 52, the wheel inside his chest. Round 3: 55, a small wheel
    hidden behind his arm and the pipe, the balloon at the frame edge.)"""
    where = place("gas_field")
    data = load_data(); data.place(-0.12, 0.1, 0)
    L, R = sides(data)
    shR = acts._shoulder(data, R)
    # a BIG wheel beside his hip, facing us, nothing in front of it. He works the top-left of its rim (the arc
    # nearest his shoulder), so the wheel can be big and still in his reach: a quarter turn a push.
    STEM, WR, SA = 0.17, 0.08, math.radians(50)                   # on a branch from the pipe, which stands off to
    WC = shR + Vector((0.1, -0.1, -0.165))                        # his right, its balloon clear of his head
    HW = WC.z + 0.02
    WH = WC - (Vector((-math.sin(SA), -math.cos(SA), 0)) * STEM + Vector((0, 0, HW - 0.02))); WH.z = 0.0
    root, wheel, neck_l, wc_l, WR = HK.crank_wellhead("wellhead", tuple(WH), h=HW, stem=STEM, WR=WR, front=True,
                                                      neck_h=0.16, stem_a=SA)   # a riser: the full balloon up by his face
    NECK = WH + neck_l; WC = WH + wc_l
    T_TURN0, T_TURN1 = 0.4, DUR - 1.25
    A_HI, A_LO = math.radians(165), math.radians(85)              # the arc of rim he pushes, top-left to the top
    STROKE, NS = A_HI - A_LO, 3
    D = (T_TURN1 - T_TURN0) / NS
    # each stroke is ONE LOOP of the hand, like rowing: along the rim pushing it round, then off the rim and back up
    # for the next grip, the velocity never snapping at either end (pushes that stopped dead and reversed stuttered)
    def phase(t):
        k = min(float(NS), max(0.0, (t - T_TURN0) / D)); n = min(NS - 1, int(k)); return n, math.tau * (k - n), k >= NS
    def spin(t):
        n, ph, done = phase(t)
        if done: return STROKE * NS
        return STROKE * (n + (0.5 - 0.5 * math.cos(ph) if ph < math.pi else 1.0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; wheel.rotation_euler = (0, spin(t), 0); wheel.keyframe_insert("rotation_euler", frame=f)
    def grip(t):
        n, ph, done = phase(t)
        if t < T_TURN0 or done: ph = 0.0 if t < T_TURN0 else math.pi
        a = (A_HI + A_LO) / 2 + (STROKE / 2) * math.cos(ph)
        off = max(0.0, -math.sin(ph)) ** 2
        return WC + Vector((WR * math.cos(a), -0.022 - 0.03 * off, WR * math.sin(a) + 0.012 * off))
    reach(data, R, grip, 0.0, DUR, lead=0.05, back=None, elbow_out=0.5)
    b = HK.balloon("well balloon", tuple(NECK), r=0.14, color="#2F7FD8")
    HK.inflate(b, T_TURN0 + 0.2, T_TURN1 + 0.1, frm=0.32, droop=2.2)     # an empty skin flopped over the neck, then up and round
    data.look_at(WC, 0.0, max_yaw=35, max_pitch=40, blend=0.0)
    data.look_at(NECK + Vector((0, 0, 0.12)), T_TURN0 + 1.0, max_yaw=35, max_pitch=30)
    data.look_at(US, T_TURN1 + 0.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TURN0 + 0.9)
    data.expression("pleased", T_TURN0 + 1.6, T_TURN1)
    data.perform("happy", T_TURN1 + 0.35, hold=0.6, arms=False)
    data.finish()
    soft_key("well key", (-0.7, -1.0, 1.0), tuple(NECK + Vector((0, 0, 0.12))), energy=22, size=36)
    C0, L0 = Vector((0.06, -1.24, 0.54)), Vector((0.06, 0.0, 0.52))   # wide enough that the full balloon stays in
    C1, L1 = Vector((0.06, -1.2, 0.58)), Vector((0.06, 0.0, 0.56))
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((0.05, -0.1, 0.5))))
    return dict(**where, data=data, rest=1, grips=("wellhead",),
                conseq=[("the balloon on the wellhead fills out huge", lambda: meshes([b]), T_TURN0, DUR)])


# ================================================================ SHOT 3: escape
def shot3():
    """IT SLIPS, HE JUMPS, HE MISSES BY A HAND, IT'S GONE. Low on the dock with open sky behind: Data holds a big red
    balloon high on a taut string. A tug, and the string slides out of his fist. He crouches, springs up with his
    arm straight up and his hand passes just under the trailing end of the string, lands, and watches it climb out
    of the top of the frame; he slumps. (Round 1: 48, no visible slip, the balloon already far above when he
    jumped, feet barely off the ground, a long dead stare at a dot.)"""
    where = place("dock")
    data = load_data(); data.place(-0.02, 0.1, 0)
    L, R = sides(data)
    shR = acts._shoulder(data, R)
    T_SLIP, T_CROUCH, T_LAUNCH, T_APEX, T_LAND = 0.9, 1.12, 1.34, 1.6, 1.9
    def jump(t):                      # the body's height: crouch, launch, hang at the apex, land, absorb, settle
        keys = ((0.0, 0.0), (T_CROUCH, 0.0), (T_LAUNCH, -0.045), (T_LAUNCH + 0.12, 0.1), (T_APEX, 0.16), (T_APEX + 0.08, 0.155),
                (T_LAND, 0.0), (T_LAND + 0.1, -0.035), (T_LAND + 0.32, 0.0), (DUR, 0.0))
        for (ta, za), (tb, zb) in zip(keys, keys[1:]):
            if t <= tb:
                u = (t - ta) / max(1e-6, tb - ta)
                return za + (zb - za) * (u if za > zb and tb == T_LAND else ease(u))   # it falls, then the knees take it
        return 0.0
    arm = data.arm; z0 = arm.location.z
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; arm.location.z = z0 + jump(t); arm.keyframe_insert("location", frame=f, index=2)
    LEN = 0.22
    H0 = shR + Vector((0.1, -0.09, -0.02))                      # his fist at his chest, the balloon above his head:
                                                                 # it rises PAST his face when it slips (round 3)
    KN0 = H0 + Vector((0.0, 0.0, LEN))
    # off his hand, then away: timed so at the top of his jump the string's end hangs a hand above his reaching hand
    rise = lambda u: Vector((-0.04 * u, 0.06 * u * u, 0.33 * u + 0.18 * u * u))
    def kp(t):
        if t < T_SLIP:
            return KN0 + Vector((0.006 * math.sin(2.1 * t), 0.0, 0.004 * math.sin(3.3 * t)))
        return KN0 + rise(t - T_SLIP) + Vector((0.012 * math.sin(2.4 * t), 0, 0))
    def tail(t):                      # the string's free end: in his fist, then trailing under the balloon, swinging
        if t < T_SLIP: return H0 + Vector((0.006 * math.sin(2.1 * t), 0.0, 0.004 * math.sin(3.3 * t)))
        sw = 0.04 * math.sin(5.0 * (t - T_SLIP)) * math.exp(-1.2 * (t - T_SLIP))
        return kp(t) - Vector((sw, 0, LEN))
    b = HK.balloon("escape balloon", tuple(KN0), r=0.12, color="#D22B2B")
    follow(b, kp, 0.0, DUR)
    HK.string_between("escape string", tail, kp, NF, r=0.0024)          # thick enough to see the near miss
    # the fist: tugged up a little as it slips, then the arm drops into the crouch
    hold = lambda t: H0 + Vector((0, 0, 0.025 * ease(min(1.0, max(0.0, (t - T_SLIP + 0.06) / 0.1))))) if t < T_SLIP + 0.05 else H0
    reach(data, R, hold, 0.0, T_SLIP - 0.1, lead=0.05, back=None, elbow_out=0.4)
    # the reach: at the apex his hand is straight up, the string's end swinging just above his fingers
    # the reach is ONE move in his own frame (off his shoulder as it is on each frame): up from the fist to straight
    # overhead at the top of the jump, on through it and down to his side as he lands. Never a stop on the way up
    # (a swing that stopped dead under a moving job stuttered), never locked straight (0.18 off the shoulder).
    T_R0 = T_SLIP - 0.1
    TOPR = Vector((0.09, -0.06, 0.145))
    arc = spline([(T_R0, H0 - shR), (T_SLIP + 0.02, H0 - shR + Vector((0, 0, 0.025))), (T_APEX - 0.05, TOPR),   # the tug, then up (T_APEX + 0.07, TOPR + Vector((0, 0, -0.005))),
                  (T_LAND + 0.15, Vector((0.1, -0.09, 0.02))), (T_LAND + 0.75, Vector((0.07, -0.07, -0.13)))])
    def up(t):
        bpy.context.view_layer.update(); return acts._shoulder(data, R) + arc(t)
    reach(data, R, up, T_R0, DUR, lead=0.05, back=None, elbow_out=0.2)
    data.look_at(KN0 + Vector((0, 0, 0.1)), 0.0, max_yaw=25, max_pitch=40, blend=0.0)
    data.look_at(kp(T_APEX), T_SLIP + 0.1, max_yaw=30, max_pitch=38)   # the eyes go the rest: his face stays ours
    data.look_at(kp(T_LAND + 0.9), T_LAND + 0.2, max_yaw=30, max_pitch=40)
    data.look_at(kp(DUR), T_LAND + 1.2, max_yaw=30, max_pitch=42)
    data.look_at(US, DUR - 0.9, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_SLIP)
    data.expression("alarmed", T_SLIP + 0.04, T_LAND + 0.3, blend=0.2)
    data.perform("sad", T_LAND + 1.0, hold=1.0, arms=False)
    data.finish()
    soft_key("balloon key", (0.6, -1.0, 0.9), tuple(KN0 + Vector((0, 0, 0.1))), energy=20, size=40)
    C0, L0 = Vector((0.02, -1.08, 0.16)), Vector((0.02, 0.0, 0.6))      # low on the quay, looking up into the sky
    cam = K.camera(tuple(C0), tuple(L0), lens=24, fstop=5.6)
    camera_path(cam, lambda t: (C0, L0 + Vector((0, 0, 0.06 * ease(min(1.0, max(0.0, (t - T_SLIP) / 2.0))))), Vector((0.0, 0.0, 0.6))))
    return dict(**where, data=data, rest=1, grips=("escape",),
                conseq=[("the balloon rises out of reach and away into the sky", lambda: meshes([b]), T_SLIP, T_SLIP + 1.1, {"whole": False})])


# ================================================================ SHOT 4: the scanner
def shot4():
    """HE POURS FREEZING HELIUM INTO THE HOSPITAL SCANNER. Close on Data in front of a big white MRI scanner ring. A
    steel fill port juts out of the ring's face to a funnel beside him; he holds a steel flask by its handle
    and tips it, soft white freezing vapour pours from its lip down into the port, frost creeps out over the ring
    from where the port joins it, and the scanner's big lamp beside it switches from red to green. He looks at us,
    impressed. (Round 1: 38, the scanner hid behind him, the lamp small, the smoke stacked spheres. Round 2: 42, the
    smoke went into a funnel on a stand and pooled on the floor as flat discs, no frost on the ring, Data tiny.)"""
    where = place("hospital")
    data = load_data(); data.place(-0.16, 0.1, 0)
    L, R = sides(data)
    SR, DEP = 0.36, 0.42
    SC = Vector((0.4, 0.5, 0.0))                                  # its patient table off to the right, clear of the port
    LA = Vector((-0.19, -DEP * 0.52, SR * 1.7))                   # the lamp high on the ring, well clear of his face
    scan, stat, port_l = HK.scanner("scanner", tuple(SC), R=SR, depth=DEP, light_r=0.075, shell_hex="#7F8995",
                                    light_at=tuple(LA))           # a slate shell: white frost reads on it (round 4: on pale grey it was invisible)
    FACE_Y = SC.y - DEP * 0.5                                     # the ring's front face
    FUN = Vector((0.15, -0.04, 0.3))                             # the port's funnel mouth, right at his chest, under the lip
    J = Vector((FUN.x + 0.02, FACE_Y + 0.01, FUN.z - 0.075))     # where the port's pipe goes into the ring
    steel = HK._mat("port steel", "#A9AEB4", rough=0.25, metal=1.0)
    bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=0.02, radius2=0.08, depth=0.085, location=tuple(FUN + Vector((0, 0, -0.035))))
    fun = bpy.context.active_object; fun.name = "port funnel"; fun.data.materials.append(steel)
    for pl in fun.data.polygons: pl.use_smooth = True
    K.cyl("port elbow", tuple(FUN + Vector((0, 0, -0.075))), 0.02, 0.03, steel, v=20, bev=0.004)
    a0 = FUN + Vector((0, 0, -0.075)); d = J - a0
    pipe = K.cyl("port pipe", tuple((a0 + J) / 2), 0.022, d.length, steel, v=20, bev=0.002)
    pipe.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    K.cyl("port flange", tuple(J), 0.04, 0.014, steel, rot=(math.pi / 2, 0, 0), v=28, bev=0.003)
    fl, mouth_l = HK.dewar("flask", (0, 0, 0), r=0.045, h=0.16)
    HOLD = Vector((-0.08, -0.035, 0.3))                          # in his right hand, out at his side, nothing crossing
    POUR = Vector((-0.06, -0.04, 0.33))                          # his chest (round 3: both arms "a tangle" over it)
    T_LIFT, T_TIP0, T_TIP1, T_BACK = 0.35, 1.0, DUR - 1.7, DUR - 1.1
    fp = spline([(0.0, HOLD), (T_LIFT, HOLD), (T_TIP0, POUR), (T_TIP1, POUR), (T_BACK, HOLD)])
    tip = lambda t: 1.0 * ease(min(1.0, max(0.0, (t - T_TIP0 + 0.35) / 0.55))) * (1 - ease(min(1.0, max(0.0, (t - T_TIP1) / 0.5))))
    follow(fl, fp, 0.0, DUR, rot_fn=lambda t: (0, tip(t), 0))
    def at(local):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update(); return fl.matrix_world @ Vector(local)
        return fn
    mouth = at(mouth_l)
    puffs = HK.cold_smoke("cold", mouth, lambda t: FUN - mouth(t), T_TIP0 + 0.15, T_TIP1 - 0.3, NF, n=220, seed=4,
                          into=FUN + Vector((0, 0, -0.06)))       # down into the port, not onto the floor
    HK.frost(["port funnel", "port pipe", "port elbow", "port flange"], T_TIP0 + 0.4, T_TIP0 + 1.4)
    HK.frost_spread("scanner ring", J, T_TIP0 + 0.4, T_TIP1 + 0.2, 0.8)
    HK.status(stat, 0.0, "#E01810", emit=2.2); HK.status(stat, T_TIP1 - 0.35, "#E01810", emit=2.2)
    HK.status(stat, T_TIP1 - 0.2, "#10D040", emit=4.0); HK.status(stat, T_TIP1 + 0.2, "#10D040", emit=2.6)
    reach(data, R, at((-0.057, 0.0, 0.1)), 0.0, DUR, lead=0.05, back=None, elbow_out=0.55)   # his hand on the near handle,
    LAMP = SC + LA                                                                           # the flask turning in it
    data.look_at(fp(0.0) + Vector((0, 0, 0.12)), 0.0, max_yaw=30, max_pitch=40, blend=0.0)
    data.look_at(FUN, T_TIP0, max_yaw=35, max_pitch=40)
    data.look_at(LAMP, T_TIP1 - 0.4, max_yaw=45, max_pitch=30)
    data.look_at(US, T_BACK + 0.15, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T_TIP1 - 0.45)
    data.expression("surprised", T_TIP1 - 0.25, T_BACK, blend=0.18)
    data.expression("happy", T_BACK + 0.15, DUR + 1.0, blend=0.3)
    data.finish()
    soft_key("pour key", (-0.7, -1.0, 1.0), tuple(FUN + Vector((0, 0, 0.1))), energy=16, size=34)
    soft_key("scanner key", (1.1, -0.8, 1.4), tuple(SC + Vector((0, 0, 0.4))), energy=14, size=40, color=(0.92, 0.96, 1.0))
    C0, L0 = Vector((0.0, -1.02, 0.5)), Vector((0.0, 0.2, 0.44))     # Data on the left third, the port, the frost
    C1, L1 = Vector((0.0, -0.97, 0.5)), Vector((0.0, 0.2, 0.45))   # and the lamp on the right: all of it big
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.0, -0.05, 0.45))))
    return dict(**where, data=data, rest=1, grips=("flask", "port"),
                conseq=[("freezing vapour pours from the flask down into the scanner's port", lambda: puffs, T_TIP0 + 0.3, T_TIP1, {"whole": False}),
                        ("frost creeps over the ring and its lamp switches from red to green", lambda: meshes([scan]), T_TIP1 - 0.6, DUR, {"whole": False})])


# ================================================================ SHOT 5: payoff
def shot5():
    """HE TIES THE LAST BALLOON DOWN INSTEAD OF LETTING IT GO. Close in the party aisle, a big iron kettlebell on a
    little stand right in front of Data, between him and us: he holds a pink balloon by its string out at his side;
    his grip slips and it lifts, he snatches the string back, brings it down and winds it round the kettlebell's
    handle. The balloon tugs and bobs, held down, up beside his head. He points up at it and looks into the lens,
    one brow up: would you still buy one? (Round 1: 46, the slip never read, he pointed at nothing, the weight was
    a dark block. Round 2: 38, a wide shot where the tie was too small to see, the balloon cut by the edge. Round 3:
    42, his hand "just rests on top of the weight", no point, a static end, his head cut by the edge.)"""
    where = store_set()
    data = load_data(); data.place(0.04, 0.06, 0)
    L, R = sides(data)
    shL = acts._shoulder(data, L)
    TOP = 0.31                                                    # a little stand right in front of him, the weight on it
    WT = Vector((shL.x - 0.065, data.pos().y - 0.105, TOP))        # in front of his left side, clear of his coat, the
    SK.table("party table", (WT.x, WT.y, 0.0), w=0.15, d=0.11, h=TOP)   # handle 0.15 off his shoulder: in his reach
    w = HK.weight("weight", tuple(WT), s=0.11)
    TIE = WT + Vector((0, 0.0, w["tie"] - 0.012))
    H0 = shL + Vector((-0.09, -0.08, -0.02))                      # his fist out at his side holding the string
    T_SLIP, T_CATCH, T_DOWN, T_TIE0, T_TIE1 = 0.5, 0.8, 1.75, 1.9, 3.2
    T_OPEN = T_TIE1 + 0.65
    hp = spline([(0.0, H0), (T_SLIP, H0), (T_CATCH, H0 + Vector((-0.01, 0.0, 0.045))),       # a snatch up after the string, no dip
                 (T_DOWN, TIE + Vector((0.0, -0.014, 0.02)))])
    NRM = (TIE - shL).normalized()                                # the loop is drawn ACROSS his reach, so his arm circles
    E1 = NRM.cross(Vector((0, 0, 1))).normalized(); E2 = E1.cross(NRM).normalized()   # a cone and never stops and turns back
    def hand(t):
        if t < T_TIE0: return hp(t)
        u = min(1.0, (t - T_TIE0) / (T_TIE1 - T_TIE0))        # loops round the handle, over the top and down its
        a = math.tau * 1.5 * ease(u)                              # front, toward the lens: a winding read from the front
        return TIE + Vector((0, -0.016, 0)) + E1 * (0.03 * math.sin(a)) + E2 * (0.026 * math.cos(a))
    reach(data, L, hand, 0.0, T_TIE1, lead=0.05, back=None, elbow_out=0.45)
    LEAN = Vector((-0.1, 0.02, 0.26))                           # the string leans off to the image-left: clear of his face
    def tail(t):
        if t < T_SLIP: return hand(t)
        if t < T_CATCH:                                           # slipping: the string slides up out of his fist
            u = (t - T_SLIP) / (T_CATCH - T_SLIP); return hand(t) + Vector((0, 0, 0.07 * ease(u)))
        return hand(t) if t < T_TIE1 else TIE
    def knot(t):
        base = tail(t) + LEAN
        if t >= T_TIE1:                                           # held down: it tugs up against the weight and bobs
            k = t - T_TIE1
            base = base + Vector((0.05 * math.sin(4.0 * k) * math.exp(-0.2 * k), 0, 0.04 * math.sin(5.5 * k) * math.exp(-0.25 * k)))
        return base + bob(t, 5, 0.012)                            # it keeps tugging to the end: never a still frame (round 3)
    b = HK.balloon("last balloon", tuple(knot(0.0)), r=0.12, color="#E2559B")
    follow(b, knot, 0.0, DUR, rot_fn=lambda t: (0, -0.5, 0))    # the balloon tilts along its leaning string
    HK.string_between("last string", tail, knot, NF, r=0.003)   # thick enough to follow round the handle
    # then he points up at it: his arm out along the line from his shoulder to the tied balloon, clear of his face
    OPEN = shL + Vector((-0.11, -0.07, 0.07))                     # out and up toward it, away from his own head, the
                                                                  # elbow still soft (a straight arm locked backward)
    reach(data, L, lambda t: OPEN, T_OPEN, DUR, lead=0.65, back=None, elbow_out=0.3)
    data.look_at(knot(0.0) + Vector((0, 0, 0.1)), 0.0, max_yaw=25, max_pitch=40, blend=0.0)   # the eyes take the rest:
    data.look_at(knot(T_CATCH) + Vector((0, 0, 0.1)), T_SLIP, max_yaw=25, max_pitch=40)       # a full turn put his head into his arm
    data.look_at(TIE + Vector((0, 0, 0.03)), T_DOWN - 0.3, max_yaw=30, max_pitch=18)   # the eyes go down; a full nod put his head into his own forearm
    data.look_at(knot(DUR) + Vector((0, 0, 0.12)), T_TIE1 + 0.1, max_yaw=25, max_pitch=40)
    data.look_at(US, T_OPEN + 0.45, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_SLIP)
    data.expression("surprised", T_SLIP + 0.04, T_CATCH + 0.25, blend=0.2)
    data.expression("determined", T_DOWN - 0.1, T_TIE1)
    data.expression("pleased", T_TIE1 + 0.15, T_OPEN + 0.3)
    data.expression("surprised", T_OPEN + 0.4, DUR + 1.0, blend=0.25)   # brows up, into the lens
    data.finish()
    soft_key("table key", (-0.6, -1.0, 1.0), tuple(TIE + Vector((0, 0, 0.2))), energy=24, size=36)
    C0, L0 = Vector((-0.14, -1.12, 0.62)), Vector((-0.14, 0.0, 0.6))  # close: the weight, the tie, his face and
    C1, L1 = Vector((-0.13, -1.04, 0.63)), Vector((-0.13, 0.0, 0.61))     # the whole balloon, all in the frame
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=5.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((-0.09, -0.1, 0.55))))
    return dict(**where, data=data, rest=1, grips=("last", "weight"),
                conseq=[("the string is wound round the kettlebell's handle", lambda: meshes([w]), T_TIE0, DUR, {"whole": False}),
                        ("the balloon tugs and bobs, held down by the kettlebell", lambda: meshes([b]), T_TIE1, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
