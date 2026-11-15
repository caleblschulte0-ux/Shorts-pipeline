"""THE HELIUM SHORT (the fourth 3D short, 2026-11-15): the gas in party balloons is running out, and we can't make
more. Made end to end without a sign-off (caaleb, 2026-11-15: "start working on a new video and all the new fixes"),
each beat its own place and its own idea (script.json `sets`, `ideas`), every prop big and right in front of him.

  1 hook     store      one big balloon beside his face goes limp and sags in his hand
  2 the well gas_field  he turns a wellhead wheel and gas from the ground swells a balloon on the pipe
  3 escape   dock       he jumps for an escaping balloon and it gets away into the sky
  4 the job  hospital   he pours a smoking flask of freezing helium into a giant scanner
  5 payoff   store      the last balloon on his wrist, he shrugs at us: would you still buy one?

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
    SAG = H0 + Vector((-0.005, 0.0, -0.035))                     # the arm sinks with it as it sags
    H = spline([(0.0, H0), (T_GO, H0), (T_DROP + 0.6, SAG), (T_UP0, SAG + Vector((0, 0, 0.005))), (T_UP1, H1)])
    reach(data, L, H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    U = Vector((-0.1, -0.03, 0.19))                               # lower: the whole balloon in frame (round 7: cut)                              # the balloon right beside his face, image-left of it
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
    C0, L0 = Vector((-0.08, -0.7, 0.62)), Vector((-0.08, 0.0, 0.6))     # waist up (round 7: full body)
    C1, L1 = Vector((-0.07, -0.63, 0.6)), Vector((-0.07, 0.0, 0.58))   # waist up, then a push in on his face
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
    STEM, WR, SA = 0.14, 0.052, math.radians(88)                  # on a branch from the pipe, which stands off to
    WC = shR + Vector((0.03, -0.11, -0.08))                        # his right, the wheel in front of his chest: the
    HW = WC.z + 0.02                                              # knob's whole circle inside his reach
    WH = WC - (Vector((-math.sin(SA), -math.cos(SA), 0)) * STEM + Vector((0, 0, HW - 0.02))); WH.z = 0.0
    root, wheel, neck_l, wc_l, WR = HK.crank_wellhead("wellhead", tuple(WH), h=HW, stem=STEM, WR=WR, front=True,
                                                      neck_h=0.16, stem_a=SA, gauge=True)   # a riser: the full balloon up by his face
    NECK = WH + neck_l; WC = WH + wc_l
    T_TURN0, T_TURN1 = 0.45, DUR - 1.25
    TURNS = 1.25                                                  # a turn and a quarter, his hand ON the knob all the way
    def spin(t):                                                  # round: never let go, never back up (round 5-7:
        u = min(1.0, max(0.0, (t - T_TURN0) / (T_TURN1 - T_TURN0)))   # "his hand is not on the red crank handle")
        return math.tau * TURNS * (u * u * (3 - 2 * u))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; wheel.rotation_euler = (0, spin(t), 0); wheel.keyframe_insert("rotation_euler", frame=f)
    def grip(t):                                                  # the knob, where the wheel has carried it
        th = spin(t)
        return WC + Vector((WR * math.cos(th), -0.045, -WR * math.sin(th)))
    reach(data, R, grip, 0.0, T_TURN1 + 0.25, lead=0.05, back=0.9, elbow_out=0.4)   # then lets go
    b = HK.balloon("well balloon", tuple(NECK), r=0.14, color="#2F7FD8")
    HK.inflate(b, T_TURN0 + 0.2, T_TURN1 + 0.1, frm=0.22, droop=0.7)     # an empty skin flopped over the neck, then up and round
    data.look_at(WC, 0.0, max_yaw=35, max_pitch=40, blend=0.0)
    data.look_at(NECK + Vector((0, 0, 0.12)), T_TURN0 + 1.0, max_yaw=35, max_pitch=30)
    data.look_at(US, T_TURN1 + 0.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TURN0 + 0.9)
    data.expression("pleased", T_TURN0 + 1.6, T_TURN1)
    data.perform("happy", T_TURN1 + 0.35, hold=0.6, arms=False)
    data.finish()
    soft_key("well key", (-0.7, -1.0, 1.0), tuple(NECK + Vector((0, 0, 0.12))), energy=22, size=36)
    C0, L0 = Vector((-0.07, -1.0, 0.54)), Vector((-0.07, 0.0, 0.52))   # his head well inside the left edge   # wide enough that the full balloon stays in
    C1, L1 = Vector((-0.06, -1.06, 0.6)), Vector((-0.06, 0.0, 0.58))
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
    iron = HK._mat("bollard iron", "#2E3236", rough=0.45, metal=0.7)       # a mooring bollard and its rope: a dock
    K.cyl("bollard", (0.24, 0.2, 0.05), 0.04, 0.1, iron, v=28, bev=0.006)
    K.cyl("bollard cap", (0.24, 0.2, 0.105), 0.055, 0.016, iron, v=28, bev=0.005)
    rope = HK._mat("bollard rope", "#C9AE7A", rough=0.8)
    K.cyl("bollard rope", (0.24, 0.2, 0.075), 0.043, 0.014, rope, v=28, bev=0.004)
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
    data.look_at(kp(T_APEX), T_SLIP + 0.1, max_yaw=30, max_pitch=26)   # the eyes go the rest: his face stays ours
    data.look_at(kp(T_LAND + 0.9), T_LAND + 0.2, max_yaw=30, max_pitch=28)   # the eyes look up, the head tips
    data.look_at(kp(DUR), T_LAND + 1.2, max_yaw=30, max_pitch=30)            # less: his face reads (round 7)
    data.look_at(US, DUR - 0.9, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_SLIP)
    data.expression("alarmed", T_SLIP + 0.04, T_LAND + 0.3, blend=0.2)
    data.perform("sad", T_LAND + 1.0, hold=1.0, arms=False)
    data.finish()
    soft_key("balloon key", (0.6, -1.0, 0.9), tuple(KN0 + Vector((0, 0, 0.1))), energy=20, size=40)
    C0, L0 = Vector((0.02, -0.98, 0.08)), Vector((0.02, 0.0, 0.7))      # low on the quay, looking up into the sky
    cam = K.camera(tuple(C0), tuple(L0), lens=22, fstop=5.6)                  # his feet in (round 7)
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
    data = load_data(); data.place(-0.08, 0.1, 0)
    L, R = sides(data)
    SR, DEP = 0.32, 0.42
    SC = Vector((0.26, 0.62, 0.0))                                  # its patient table off to the right, clear of the port
    LA = Vector((-0.06, -DEP * 0.52, SR * 1.75))                   # the lamp high on the ring, well clear of his face
    scan, stat, port_l = HK.scanner("scanner", tuple(SC), R=SR, depth=DEP, light_r=0.075, shell_hex="#7F8995",
                                    light_at=tuple(LA))           # a slate shell: white frost reads on it (round 4: on pale grey it was invisible)
    FACE_Y = SC.y - DEP * 0.5                                     # the ring's front face
    FUN = Vector((0.23, -0.04, 0.3))                             # the port's funnel mouth, right at his chest, under the lip
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
    HOLD = Vector((0.04, -0.07, 0.3))                            # in his right hand, out at his side, nothing crossing
    POUR = Vector((0.02, -0.04, 0.33))                           # his chest (round 3: both arms "a tangle" over it)
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
    C0, L0 = Vector((0.12, -1.12, 0.52)), Vector((0.12, 0.2, 0.46))   # Data on the left third, the port, the frost
    C1, L1 = Vector((0.12, -1.08, 0.52)), Vector((0.12, 0.2, 0.47))    # and the whole ring on the right (round 5: cut)
    cam = K.camera(tuple(C0), tuple(L0), lens=25, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.0, -0.05, 0.45))))
    return dict(**where, data=data, rest=1, grips=("flask", "port"),
                conseq=[("freezing vapour pours from the flask down into the scanner's port", lambda: puffs, T_TIP0 + 0.3, T_TIP1, {"whole": False}),
                        ("frost creeps over the ring and its lamp switches from red to green", lambda: meshes([scan]), T_TIP1 - 0.6, DUR, {"whole": False})])


# ================================================================ SHOT 5: payoff
def shot5():
    """WOULD YOU STILL BUY ONE? Close, chest up, in the party aisle: one pink balloon floats over his shoulder, its
    string tied round his wrist. He looks up at it, then at us, and SHRUGS: arms bent down, hands out, palms up,
    eyebrows up, a questioning face held for a second while the balloon bobs on his wrist. The shrug is the question.
    (Rounds 1-5, tying it to a kettlebell: 46, 38, 42, 46, 48. Rounds 6-7, holding it out to the lens: 42, 40, the
    hand could never come forward without his arm or the balloon passing through his head.)"""
    where = store_set()
    data = load_data(); data.place(0.1, 0.06, 0)
    L, R = sides(data)
    shL = acts._shoulder(data, L)
    T_TURN, T_SHRUG = 1.5, 2.0
    HOLD_S = DUR - T_SHRUG - 0.75                                                 # the question held, then he lets it hang
    data.look_at(shL + Vector((-0.13, -0.02, 0.4)), 0.0, max_yaw=30, max_pitch=50, blend=0.0)   # up at it
    data.look_at(US, T_TURN, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TURN)
    data.act("shrug", T_SHRUG, dur=0.35, hold=HOLD_S)
    data.expression("surprised", T_SHRUG + 0.35 + HOLD_S, DUR + 1.0, blend=0.3)   # the question stays on his face
    data.finish()
    W = {f: data._wrist(L, f) for f in range(1, NF + 1)}           # the string is tied round his wrist: it goes
    def wrist(t): return W[max(1, min(NF, F(t)))]                  # wherever the shrug takes his hand
    LEAN = Vector((-0.13, -0.02, 0.26))                            # up over his shoulder on the image-left, clear of his head
    def knot(t):
        k = max(0.0, t - T_SHRUG)
        sw = Vector((0.025 * math.sin(3.4 * k) * math.exp(-0.3 * k), 0, 0.02 * math.sin(4.6 * k) * math.exp(-0.35 * k)))
        return wrist(t) + LEAN + sw + bob(t, 5, 0.01)
    b = HK.balloon("wrist balloon", tuple(knot(0.0)), r=0.1, color="#E2559B")
    follow(b, knot, 0.0, DUR, rot_fn=lambda t: (0, -0.35, 0))
    HK.string_between("wrist string", wrist, knot, NF, r=0.0024)
    soft_key("shrug key", (-0.6, -1.0, 1.0), tuple(shL + Vector((0, 0, 0.1))), energy=24, size=36)
    C0, L0 = Vector((-0.07, -0.8, 0.62)), Vector((-0.07, 0.0, 0.6))   # chest up, the balloon whole in frame
    C1, L1 = Vector((-0.06, -0.74, 0.61)), Vector((-0.06, 0.0, 0.59))
    cam = K.camera(tuple(C0), tuple(L0), lens=30, fstop=4.5)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((-0.06, -0.1, 0.58))))
    return dict(**where, data=data, rest=1, grips=("wrist",),
                conseq=[("he shrugs at us, palms up, the balloon on his wrist: would you?", lambda: meshes([b]), T_SHRUG, DUR, {"whole": False})])

SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
