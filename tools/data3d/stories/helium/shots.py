"""THE HELIUM SHORT (the fourth 3D short, 2026-11-15): the gas in party balloons is running out, and we can't make
more. Made end to end without a sign-off (caaleb, 2026-11-15: "start working on a new video and all the new fixes"),
each beat its own place and its own idea (script.json `sets`, `ideas`), every prop big and right in front of him.

  1 hook     store      one big balloon beside his face goes limp and sags in his hand
  2 the well gas_field  he turns a wellhead wheel and gas from the ground swells a balloon on the pipe
  3 escape   dock       he jumps for an escaping balloon and it gets away into the sky
  4 the job  hospital   he ties one of his four balloons to a giant scanner and it frosts cold
  5 payoff   store      he holds the last balloon out to us: would you still buy one?

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
    """THE BALLOON SAGS IN HIS HAND. Close, waist up: Data holds ONE big red balloon by its string, right beside his
    face. He smiles at it; then it goes limp, sags in on itself and drops down its string to hang off his fist like
    a wet sock. His face falls with it, and he looks at us, alarmed. (Rounds 1-5, a bunch of six shrivelling one by
    one: 52, 30, 60, 55, 63. The coordinator's 180: one big balloon, one change.)"""
    where = store_set()
    data = load_data(); data.place(0.04, 0.08, 0)
    L, R = sides(data)
    sh = acts._shoulder(data, L)
    H0 = sh + Vector((-0.08, -0.11, 0.0))                        # his fist up at his shoulder on the image-left
    H1 = sh + Vector((-0.07, -0.13, 0.03))                       # held up a little to show us what is left
    T_GO, T_DROP = 0.9, 1.4
    T_UP0 = T_DROP + 1.0; T_UP1 = T_UP0 + 0.6
    H = spline([(0.0, H0), (T_UP0, H0), (T_UP1, H1)])
    reach(data, L, H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    U = Vector((-0.08, -0.02, 0.27))                              # the balloon right beside his face, image-left of it
    b = HK.balloon("big balloon", (0, 0, 0), r=0.15, color=COLORS[0])
    HK.shrivel(b, T_GO, T_GO + 0.7, to=0.45, seed=1, hang=True)
    END = Vector((-0.012, -0.02, -0.11))                          # it hangs straight down under his fist
    def kp(t):
        k = ease(min(1.0, max(0.0, (t - T_DROP) / 0.9)))
        if k <= 0: return H(t) + U + bob(t, 0) * (1.0 if t < T_GO else 0.4)
        mid = Vector((U.x * 0.9, U.y, (U.z + END.z) * 0.5))
        return H(t) + U * (1 - k) ** 2 + mid * 2 * k * (1 - k) + END * k * k
    follow(b, kp, 0.0, DUR)
    HK.string_between("big string", H, kp, NF, r=0.0022)
    data.look_at(H0 + U + Vector((0, 0, 0.05)), 0.0, max_yaw=22, max_pitch=25, blend=0.0)
    data.look_at(H0 + Vector((-0.04, 0, -0.06)), T_DROP + 0.3, max_yaw=22, max_pitch=30)
    data.look_at(US, T_UP0 + 0.1, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("happy", 0.0, T_GO)
    data.expression("worried", T_GO + 0.2, T_UP0)
    data.expression("alarmed", T_UP0 + 0.1, DUR + 1.0, blend=0.15)
    data.finish()
    soft_key("bunch key", (-0.7, -1.0, 1.1), tuple(H0 + Vector((-0.05, 0, 0.2))), energy=26, size=34)
    C0, L0 = Vector((-0.05, -0.92, 0.6)), Vector((-0.05, 0.0, 0.58))
    C1, L1 = Vector((-0.04, -0.82, 0.57)), Vector((-0.04, 0.0, 0.55))   # waist up, then a push in on his face
    cam = K.camera(tuple(C0), tuple(L0), lens=28, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / DUR))), L0.lerp(L1, ease(min(1.0, t / DUR))), Vector((-0.06, -0.1, 0.6))))
    return dict(**where, data=data, rest=1, grips=("big",),
                conseq=[("the big balloon goes limp and sags off his fist", lambda: meshes([b]), T_GO, DUR)])


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
    C0, L0 = Vector((0.1, -1.24, 0.54)), Vector((0.1, 0.0, 0.52))   # wide enough that the full balloon stays in
    C1, L1 = Vector((0.1, -1.2, 0.58)), Vector((0.1, 0.0, 0.56))
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
    rise = lambda u: Vector((-0.04 * u, 0.12 * u * u, 0.3 * u + 0.12 * u * u))   # away AND up: it shrinks in frame
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
    arc = spline([(T_R0, H0 - shR), (T_SLIP + 0.02, H0 - shR + Vector((0, 0, 0.025))), (T_APEX - 0.05, TOPR),   # the tug, then up and on through the top: no second key there
                  
                  (T_LAND + 0.15, Vector((0.1, -0.09, 0.02))), (T_LAND + 0.75, Vector((0.07, -0.07, -0.13)))])
    def up(t):
        bpy.context.view_layer.update(); return acts._shoulder(data, R) + arc(t)
    reach(data, R, up, T_R0, DUR, lead=0.05, back=None, elbow_out=0.2)
    # and the other arm goes up with it: a two-handed lunge (round 5: "only one arm up")
    arcL = spline([(T_SLIP + 0.12, Vector((-0.08, -0.08, -0.06))), (T_APEX - 0.04, Vector((-0.14, -0.08, 0.07))),
                   (T_APEX + 0.07, Vector((-0.14, -0.08, 0.065))), (T_LAND, Vector((-0.12, -0.08, 0.02)))])
    def upL(t):
        bpy.context.view_layer.update(); return acts._shoulder(data, L) + arcL(t)
    reach(data, L, upL, T_SLIP + 0.12, T_LAND, lead=0.45, back=0.5, elbow_out=0.4)   # then it drops back to his side
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
    C0, L0 = Vector((0.02, -0.98, 0.08)), Vector((0.02, 0.0, 0.7))      # low on the quay, looking up into the sky
    cam = K.camera(tuple(C0), tuple(L0), lens=24, fstop=5.6)
    camera_path(cam, lambda t: (C0, L0 + Vector((0, 0, 0.06 * ease(min(1.0, max(0.0, (t - T_SLIP) / 2.0))))), Vector((0.0, 0.0, 0.6))))
    return dict(**where, data=data, rest=1, grips=("escape",),
                conseq=[("the balloon rises out of reach and away into the sky", lambda: meshes([b]), T_SLIP, T_SLIP + 1.1, {"whole": False})])


# ================================================================ SHOT 4: the scanner
def shot4():
    """ONE OF FOUR KEEPS THE SCANNER COLD. Close on Data beside a big slate MRI scanner ring, a bunch of FOUR balloons
    in his fist. A steel cleat juts from the ring's face right at his hand; he winds ONE of the four strings round
    it and draws his fist back with the other three. The tied balloon bobs at the scanner, frost creeps white over
    the ring from the cleat, and the scanner's lamp switches from red to green. He holds up his three and looks at
    us. (Rounds 1-4, a flask pouring cold vapour into a port: 38, 42, 48, 52. The coordinator's 180: one action, the
    quarter countable, and it is balloons again.)"""
    where = place("hospital")
    data = load_data(); data.place(-0.12, 0.1, 0)
    L, R = sides(data)
    shR = acts._shoulder(data, R)
    SR, DEP = 0.25, 0.36
    SC = Vector((0.2, 0.45, 0.0))
    LA = Vector((SR * 0.6, -DEP * 0.52, SR * 1.75))                     # the lamp high on the ring, clear of the balloons
    scan, stat, port_l = HK.scanner("scanner", tuple(SC), R=SR, depth=DEP, light_r=0.075, shell_hex="#7F8995",
                                    light_at=tuple(LA))           # a slate shell: white frost reads on it
    FACE_Y = SC.y - DEP * 0.5
    CL = shR + Vector((0.12, -0.07, -0.07))                       # the cleat, right at his hand: in his reach
    J = Vector((CL.x + 0.03, FACE_Y + 0.01, CL.z - 0.03))         # where its bracket goes into the ring
    steel = HK._mat("cleat steel", "#A9AEB4", rough=0.25, metal=1.0)
    d = J - CL
    arm = K.cyl("cleat bracket", tuple((CL + J) / 2), 0.016, d.length, steel, v=20, bev=0.002)
    arm.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    K.cyl("cleat bar", tuple(CL), 0.011, 0.07, steel, rot=(0, math.pi / 2, 0), v=20, bev=0.003)
    K.cyl("cleat flange", tuple(J), 0.035, 0.014, steel, rot=(math.pi / 2, 0, 0), v=28, bev=0.003)
    T_DOWN, T_TIE0, T_TIE1, T_BACK = 1.05, 1.05, 2.2, 2.85   # straight into the loop: no stop on the way in
    HOLD = shR + Vector((0.09, -0.1, -0.04))                      # the bunch held out in front of him, right side
    UPH = shR + Vector((0.1, -0.1, -0.02))                        # and held up after: three left
    TIE = CL + Vector((0.0, -0.014, 0.012))
    hp = spline([(0.0, HOLD), (0.35, HOLD), (T_DOWN, TIE + Vector((0, -0.006, 0.036)))])     # the top of the first loop
    back = spline([(T_TIE1, TIE + Vector((0, -0.006, -0.014))), (T_BACK, UPH),   # from where the last loop ends
                   (DUR, UPH + Vector((0, 0, 0.006)))])
    NRM = Vector((1, 0, 0)); E1 = Vector((0, -1, 0)); E2 = Vector((0, 0, 1))   # round the bar's axis, toward the lens
    def fist(t):
        if t < T_TIE0: return hp(t)
        if t < T_TIE1:
            u = (t - T_TIE0) / (T_TIE1 - T_TIE0); a = math.tau * 1.5 * (1 - (1 - u) ** 2)   # moving as it arrives
            return TIE + Vector((0, -0.006, 0.016 * (1 - u))) + E1 * (0.024 * math.sin(a)) + E2 * (0.02 * math.cos(a) * (1 - 0.3 * u))
        return back(t)
    reach(data, R, fist, 0.0, DUR, lead=0.05, back=None, elbow_out=0.5)
    UP = [Vector(v) for v in ((0.12, -0.03, 0.25), (0.2, 0.0, 0.29), (0.12, 0.04, 0.34), (0.17, -0.06, 0.18))]   # off to the scanner side, clear of his head
    balloons = []
    for i, u in enumerate(UP):
        b = HK.balloon(f"four balloon {i}", (0, 0, 0), r=0.095, color=COLORS[i])
        if i == 0:                                                # the one he ties: it stays at the cleat and bobs
            tail = lambda t: fist(t) if t < T_TIE1 else CL
            def kp(t, u=u):
                if t < T_TIE1: return fist(t) + u + bob(t, 0)
                k = t - T_TIE1
                return CL + Vector((0.16, 0.04, 0.22)) + Vector((0.03 * math.sin(4.0 * k) * math.exp(-0.5 * k), 0,
                                                                0.025 * math.sin(5.2 * k) * math.exp(-0.5 * k))) + bob(t, 0)
        else:
            tail = fist
            def kp(t, u=u, i=i): return fist(t) + u + bob(t, i)
        follow(b, kp, 0.0, DUR)
        HK.string_between(f"four string {i}", tail, kp, NF, r=0.0022)
        balloons.append(b)
    HK.frost(["cleat bracket", "cleat bar", "cleat flange"], T_TIE1 + 0.1, T_TIE1 + 0.9)
    HK.frost_spread("scanner ring", J, T_TIE1 + 0.2, DUR - 0.5, 0.85)
    T_G = T_TIE1 + 1.1
    HK.status(stat, 0.0, "#E01810", emit=2.2); HK.status(stat, T_G - 0.15, "#E01810", emit=2.2)
    HK.status(stat, T_G, "#10D040", emit=4.0); HK.status(stat, T_G + 0.4, "#10D040", emit=2.6)
    LAMP = SC + LA
    data.look_at(HOLD + Vector((0, 0, 0.25)), 0.0, max_yaw=30, max_pitch=35, blend=0.0)
    data.look_at(CL, 0.6, max_yaw=35, max_pitch=40)
    data.look_at(LAMP, T_G - 0.5, max_yaw=45, max_pitch=30)
    data.look_at(US, T_G + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, 0.6)
    data.expression("determined", 0.8, T_TIE1)
    data.expression("surprised", T_G - 0.2, T_G + 0.6, blend=0.18)
    data.expression("happy", T_G + 0.7, DUR + 1.0, blend=0.3)
    data.finish()
    soft_key("bunch key", (-0.7, -1.0, 1.0), tuple(CL + Vector((0, 0, 0.2))), energy=16, size=34)
    soft_key("scanner key", (1.1, -0.8, 1.4), tuple(SC + Vector((0, 0, 0.4))), energy=14, size=40, color=(0.92, 0.96, 1.0))
    C0, L0 = Vector((0.1, -1.3, 0.5)), Vector((0.1, 0.2, 0.42))      # the whole ring and Data both in frame
    C1, L1 = Vector((0.1, -1.24, 0.5)), Vector((0.1, 0.2, 0.43))
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.1, -0.05, 0.45))))
    return dict(**where, data=data, rest=1, grips=("four", "cleat"),
                conseq=[("one of his four balloons is tied to the scanner", lambda: meshes([balloons[0]]), T_TIE1, DUR, {"whole": False}),
                        ("frost creeps over the ring and its lamp switches from red to green", lambda: meshes([scan]), T_TIE1 + 0.3, DUR, {"whole": False})])


# ================================================================ SHOT 5: payoff
def shot5():
    """WOULD YOU STILL BUY ONE? Close on Data holding one pink balloon by its string. He looks up at it, then turns to
    us and holds it out TOWARD THE LENS, offering it, eyebrows up, a questioning face held to the end while the
    balloon bobs on its string. One gesture, and it is the question. (Rounds 1-4, tying it to a kettlebell: 46, 38,
    42, 46. The coordinator's 180.)"""
    where = store_set()
    data = load_data(); data.place(0.07, 0.06, 0)
    L, R = sides(data)
    shL = acts._shoulder(data, L)
    H0 = shL + Vector((-0.07, -0.06, -0.08))                      # his fist at his side, the balloon up over it
    OFFER = shL + Vector((-0.03, -0.15, -0.05))                   # held out toward the lens: in his reach, elbow soft
    T_LOOK, T_TURN, T_OUT0, T_OUT1 = 0.2, 1.5, 1.7, 2.6
    T_NUDGE = 3.9
    hp = spline([(0.0, H0), (T_OUT0, H0), (T_OUT1, OFFER), (T_NUDGE - 0.3, OFFER + Vector((0, 0, 0.004))),
                 (T_NUDGE, OFFER + Vector((0, -0.012, 0.01))), (T_NUDGE + 0.5, OFFER + Vector((0, -0.004, 0.006))),
                 (DUR, OFFER + Vector((0, -0.004, 0.008)))])        # a little "well?" push forward, then held
    reach(data, L, hp, 0.0, DUR, lead=0.05, back=None, elbow_out=0.35)
    LEAN = Vector((-0.08, -0.05, 0.17))                           # the balloon up over his fist, toward the middle
    def knot(t):
        k = max(0.0, t - T_OUT1)
        sw = Vector((0.02 * math.sin(3.6 * k) * math.exp(-0.25 * k), 0, 0.012 * math.sin(5.0 * k) * math.exp(-0.3 * k)))
        return hp(t) + LEAN + sw + bob(t, 5, 0.01)
    b = HK.balloon("offered balloon", tuple(knot(0.0)), r=0.1, color="#E2559B")
    follow(b, knot, 0.0, DUR, rot_fn=lambda t: (0, -0.3, 0))
    HK.string_between("offered string", hp, knot, NF, r=0.0024)
    data.look_at(knot(0.0) + Vector((0, 0, 0.14)), 0.0, max_yaw=25, max_pitch=45, blend=0.0)   # head up at it
    data.look_at(US, T_TURN, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TURN)
    data.expression("wry", T_OUT0 + 0.1, DUR + 1.0, blend=0.3)          # brows up: the question, held
    data.finish()
    soft_key("offer key", (-0.6, -1.0, 1.0), tuple(OFFER + Vector((0, 0, 0.2))), energy=24, size=36)
    C0, L0 = Vector((-0.04, -0.98, 0.62)), Vector((-0.04, 0.0, 0.6))   # Data right of centre, the balloon in frame
    C1, L1 = Vector((-0.04, -0.9, 0.61)), Vector((-0.04, 0.0, 0.59))   # a slow push in on the question
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=4.5)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.0, -0.1, 0.55))))
    return dict(**where, data=data, rest=1, grips=("offered",),
                conseq=[("he holds the balloon out toward us, asking", lambda: meshes([b]), T_OUT1, DUR, {"whole": False})])

SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
