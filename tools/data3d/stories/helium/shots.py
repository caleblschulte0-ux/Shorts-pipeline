"""THE HELIUM SHORT (the fourth 3D short, 2026-11-15): the gas in party balloons is running out, and we can't make
more. Made end to end without a sign-off (caaleb, 2026-11-15: "start working on a new video and all the new fixes").

THE COUNTER STORYBOARD (round 11 on): ten rounds of wide, outdoor and full-size stagings (a wellhead in a field, a jump
on a dock, a life-size MRI, a shrug in a portrait crop) never fit a portrait phone frame: Data came out small, or the
prop or his head was cut. Every passing shot this channel has made (saffron 70-74) is a CLOSE TABLETOP shot: Data
chest up behind a counter, the idea's prop big between him and the lens. So every beat is one now, each in its place.

  1 hook     store      one big balloon beside his face goes limp and sags in his hand
  2 the well gas_field  on a field table, a glass cutaway of rock layers (glowing radioactive specks at the bottom):
                        he opens its red tap and a balloon on its pipe swells big with the gas from the rock
  3 escape   dock       at a crate on the dock the string slips through his fingers; he grabs and misses by a hand,
                        and it rises out of the top of the frame
  4 the job  hospital   on a cart, a model MRI scanner: he pours a smoking flask into its port, frost spreads over the
                        ring and its big lamp goes from red to green
  5 payoff   store      the balloon in one hand, the scanner beside it: he looks from one to the other, then at us,
                        brow up, and lifts the balloon a little toward us: would you still buy one?

Run through the shot harness (store/shots.py, STORY=helium). The props are store/helium_kit.py."""
import helium_kit as HK
import saffron_kit as SK
import locations as LOC

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




def counter(name="counter", y=-0.26, w=0.95, d=0.3, h=TABLE_H):
    """the counter he stands behind: its back edge just in front of his belly, so what sits on it is in his reach"""
    SK.table(name, (0.0, y, 0.0), w=w, d=d, h=h)
    return h


# ================================================================ SHOT 1: the hook
def shot1():
    """THE BALLOON SAGS IN HIS HAND. Close, chest up: Data holds ONE big red balloon by its string, right beside his
    face. He smiles at it; then it goes limp, sags in on itself and droops down its string to hang off his fist like
    a wet sock. His face falls with it, and he looks at us, alarmed. (Rounds 1-5, a bunch of six: 52-63. Round 6-9,
    one balloon: 72, 72, 72, 71, "framed full body", "the top cut early", "deflates in two frames".)"""
    where = store_set()
    data = load_data(); data.place(0.04, 0.08, 0)
    L, R = sides(data)
    counter("party counter")
    sh = acts._shoulder(data, L)
    H0 = sh + Vector((-0.08, -0.11, 0.0))                        # his fist up at his shoulder on the image-left
    H1 = sh + Vector((-0.08, -0.14, 0.03))                       # held up to show us what is left, hanging off its string
    T_GO, T_DROP = 0.75, 1.3
    T_UP0 = T_DROP + 0.75; T_UP1 = T_UP0 + 0.6                    # his eyes snap to us as it finishes drooping
    H = spline([(0.0, H0), (T_UP0, H0), (T_UP1, H1)])
    reach(data, L, H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    U = Vector((-0.105, -0.02, 0.19))                             # the balloon right beside his face, clear of his glasses
    b = HK.balloon("big balloon", (0, 0, 0), r=0.115, color=COLORS[0])
    HK.shrivel(b, T_GO, T_GO + 1.15, to=0.45, seed=1, hang=True, fold="front")  # it goes over a second, not two frames
    END = Vector((-0.012, -0.02, -0.13))                          # it hangs straight down under his fist on a length of string
    def kp(t):
        k = ease(min(1.0, max(0.0, (t - T_DROP) / 1.1)))
        if k <= 0: return H(t) + U + bob(t, 0) * (1.0 if t < T_GO else 0.4)
        mid = Vector((U.x * 0.9, U.y, (U.z + END.z) * 0.5))
        return H(t) + U * (1 - k) ** 2 + mid * 2 * k * (1 - k) + END * k * k
    follow(b, kp, 0.0, DUR)
    HK.string_between("big string", H, kp, NF, r=0.0022)
    data.look_at(H0 + U + Vector((0, 0, 0.05)), 0.0, max_yaw=22, max_pitch=18, blend=0.0)
    data.look_at(H0 + Vector((-0.04, 0, -0.06)), T_DROP + 0.3, max_yaw=22, max_pitch=25)
    data.look_at(US, T_UP0 + 0.1, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("happy", 0.0, T_GO)
    data.expression("worried", T_GO + 0.2, T_UP0)
    data.expression("alarmed", T_UP0 + 0.1, DUR + 1.0, blend=0.15)
    data.finish()
    soft_key("balloon key", (-0.7, -1.0, 1.1), tuple(H0 + Vector((-0.05, 0, 0.2))), energy=26, size=34)
    C0, L0 = Vector((-0.075, -1.02, 0.72)), Vector((-0.075, 0.08, 0.64))
    C1, L1 = Vector((-0.03, -0.92, 0.69)), Vector((-0.03, 0.08, 0.62))    # chest up, then a push in on his face
    cam = K.camera(tuple(C0), tuple(L0), lens=27, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(min(1.0, t / DUR))), L0.lerp(L1, ease(min(1.0, t / DUR))), Vector((-0.06, -0.1, 0.62))))
    return dict(**where, data=data, rest=1, grips=("big",),
                conseq=[("the big balloon goes limp and sags off his fist", lambda: meshes([b]), T_GO, DUR)])


# ================================================================ SHOT 2: the well
def shot2():
    """GAS FROM THE ROCK SWELLS THE BALLOON. Out on the gas plains (pump jacks far behind), Data stands at a field
    table. On it, right in front of him, a glass case of rock layers seen edge on, its bottom band dark granite flecked
    with glowing green specks; a steel pipe stands out of its lid to a red-handled tap, and runs on to the image-right
    where a limp empty balloon hangs on its open end. He takes the red lever and swings it open; bubbles rise up out of
    the glowing rock through the layers, and the balloon on the pipe stands up and swells huge and round. He looks at
    us, pleased."""
    where = place("gas_field")
    data = load_data(); data.place(-0.1, 0.0, 0)
    L, R = sides(data)
    top = counter("field table", y=-0.22, d=0.24)
    shR = acts._shoulder(data, R)
    core = HK.rock_core("rock core", (0.04, -0.2, top), w=0.24, d=0.12, h=0.11, seed=3)
    CT = Vector((0.04, -0.2, top + core["top"]))
    steel = HK._mat("gas pipe steel", "#9AA0A6", rough=0.3, metal=1.0)
    VX = shR.x + 0.06; VY = -0.1; VZ = CT.z + 0.04                # the tap: in front of his right shoulder, in reach
    K.cyl("gas pipe up", (VX, -0.2, (CT.z + VZ) / 2), 0.011, VZ - CT.z, steel, v=16, bev=0.001)
    K.sph("gas pipe bend", (VX, -0.2, VZ), 0.012, steel, seg=16, ring=8)
    K.cyl("gas pipe to tap", (VX, (VY - 0.2) / 2, VZ), 0.011, 0.2 - (-VY), steel, rot=(math.pi / 2, 0, 0), v=16, bev=0.001)
    BX = 0.17                                                     # the balloon out on the image-right, clear of his head
    K.cyl("gas pipe across", ((VX + BX) / 2, VY, VZ), 0.011, BX - VX, steel, rot=(0, math.pi / 2, 0), v=16, bev=0.001)
    RISE = 0.09
    K.sph("gas pipe elbow", (BX, VY, VZ), 0.012, steel, seg=16, ring=8)
    K.cyl("gas pipe riser", (BX, VY, VZ + RISE / 2), 0.011, RISE, steel, v=16, bev=0.001)
    K.cyl("gas pipe nozzle", (BX, VY, VZ + RISE + 0.008), 0.016, 0.016, steel, v=16, bev=0.002)
    TX = VX + 0.055                                               # the valve sits out past his elbow; the lever comes back to his hand
    tp, piv = HK.tap("tap", (TX, VY, VZ))
    T_GRAB, T_OPEN0, T_OPEN1 = 0.9, 1.0, 1.9
    ang = lambda t: math.radians(90 + 75 * ease(min(1.0, max(0.0, (t - T_OPEN0) / (T_OPEN1 - T_OPEN0)))))
    # closed: the lever stands straight up; open: he pulls it over toward himself, so his arm never crosses the valve
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; piv.rotation_euler = (0, -ang(t), 0); piv.keyframe_insert("rotation_euler", frame=f)
    LEN = 0.075
    def lever_end(t):
        a = ang(t); return Vector((TX, VY - 0.046, VZ)) + Vector((math.cos(a) * LEN * 0.85, -0.012, math.sin(a) * LEN * 0.85))
    reach(data, R, lever_end, 0.0, DUR, lead=0.05, back=None, elbow_out=0.15)   # his hand is on the lever from the first frame and stays on the open tap
    b = HK.balloon("well balloon", (BX, VY, VZ + RISE + 0.016), r=0.1, color="#2F7FD8")
    HK.inflate(b, T_OPEN1 - 0.1, T_OPEN1 + 2.1, frm=0.32, droop=2.4)
    # gas bubbles: up out of the glowing rock, through the layers, to the pipe
    bub = HK._mat("gas bubble", "#E8F6FF", rough=0.05, emit=2.0)
    rnd = __import__("random").Random(5)
    bubbles = []
    for i in range(12):
        s = core["specks"][i % len(core["specks"])]
        p0 = Vector((0.04, -0.2, top)) + Vector((s.x, s.y - 0.002, s.z))
        p1 = Vector((VX - 0.002, -0.2 - 0.061, CT.z - 0.006))
        ts = T_OPEN0 + 0.3 + i * 0.2 + rnd.uniform(-0.05, 0.05); life = rnd.uniform(0.8, 1.1)
        o = K.sph(f"bubble {i}", tuple(p0), 0.011, bub, seg=12, ring=6); bubbles.append(o)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - ts) / life
            on = 0 <= u <= 1
            q = p0.lerp(p1, ease(min(1.0, max(0.0, u)))) + Vector((0.004 * math.sin(9 * t + i), 0, 0))
            o.location = q; o.scale = (1, 1, 1) if on else (0, 0, 0)
            o.keyframe_insert("location", frame=f); o.keyframe_insert("scale", frame=f)
    data.look_at(CT, 0.0, max_yaw=25, max_pitch=25, blend=0.0)
    data.look_at(lever_end(T_GRAB) + Vector((0, 0, 0.02)), T_GRAB - 0.3, max_yaw=30, max_pitch=25)
    data.look_at(Vector((BX, VY, VZ + 0.2)), T_OPEN1 + 0.3, max_yaw=35, max_pitch=15)
    data.look_at(US, DUR - 1.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.4, T_OPEN1)
    data.expression("surprised", T_OPEN1 + 0.5, DUR - 1.4, blend=0.2)
    data.expression("pleased", DUR - 1.2, DUR + 1.0, blend=0.25)
    data.finish()
    soft_key("table key", (-0.6, -1.0, 1.0), tuple(CT + Vector((0.08, 0, 0.1))), energy=18, size=36)
    C0, L0 = Vector((0.02, -1.04, 0.7)), Vector((0.02, 0.03, 0.59))
    C1, L1 = Vector((0.02, -0.98, 0.69)), Vector((0.02, 0.03, 0.59))
    cam = K.camera(tuple(C0), tuple(L0), lens=27, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.05, -0.15, 0.55))))
    return dict(**where, data=data, rest=1, grips=("tap", "gas pipe"),
                conseq=[("the balloon on the pipe swells huge", lambda: meshes([b]), T_OPEN1, DUR)])


# ================================================================ SHOT 3: escape
def shot3():
    """IT SLIPS THROUGH HIS FINGERS AND IT'S GONE. At a crate on the dock, sea and sky behind: Data holds a big red
    balloon on a short string in his fist at his chest. A tug: his fist jerks and the string slides up out of it; he
    snatches up after it and his hand closes a hand's width under the string's end; the balloon rises out of the top
    of the frame, and he watches it go (eyes up, his face to us), then slumps, sad."""
    where = place("dock")
    data = load_data(); data.place(0.0, 0.06, 0)
    L, R = sides(data)
    top = counter("dock crate", w=0.8)
    shR = acts._shoulder(data, R)
    LEN = 0.17
    H0 = shR + Vector((0.07, -0.12, -0.07))                       # his fist in front of his chest, image-right
    KOFF = Vector((0.125, -0.02, 0.15)); LEN = KOFF.length          # the balloon up and out beside his head, never on it
    KN0 = H0 + KOFF
    T_TUG, T_SLIP, T_GRAB = 0.7, 0.9, 1.4
    # it drifts IN over his head-side shoulder as it climbs, so his snatch goes straight UP after it and closes
    # a hand's width under the string's end, not sideways at shoulder height (round 11)
    rise = lambda u: Vector((-0.09 * ease(min(1.0, u / 0.5)) + 0.02 * max(0.0, u - 0.5), 0.06 * u * u, 0.36 * u + 0.15 * u * u))
    def kp(t):
        if t < T_SLIP:
            tug = 0.04 * ease(min(1.0, max(0.0, (t - T_TUG) / 0.12)))        # a gust yanks it up
            return KN0 + Vector((0.005 * math.sin(2.1 * t), 0.0, 0.004 * math.sin(3.3 * t) + tug))
        return KN0 + Vector((0, 0, 0.02)) + rise(t - T_SLIP) + Vector((0.01 * math.sin(2.4 * t), 0, 0))
    def tail(t):                      # the string's end: in his fist, then sliding up out of it and trailing
        if t < T_SLIP: return H0 + Vector((0.005 * math.sin(2.1 * t), 0.0, 0.004 * math.sin(3.3 * t)))
        sw = 0.025 * math.sin(6.0 * (t - T_SLIP)) * math.exp(-1.5 * (t - T_SLIP))
        return kp(t) - KOFF * (1 - ease(min(1.0, (t - T_SLIP) / 0.5))) - Vector((sw, 0, LEN)) * ease(min(1.0, (t - T_SLIP) / 0.5))
    b = HK.balloon("escape balloon", tuple(KN0), r=0.11, color="#D22B2B")
    follow(b, kp, 0.0, DUR)
    HK.string_between("escape string", tail, kp, NF, r=0.0028)
    # his fist: holds, jerks up with the tug and opens (drops a little) as it slips, then snatches up after the
    # string, closing a hand under its end at T_GRAB, and comes back down to the crate
    GRAB = lambda: tail(T_GRAB) - shR - Vector((0, 0, 0.055))
    UP = Vector((0, 0, 0.045))
    arc = spline([(0.0, H0 - shR), (T_TUG, H0 - shR), (T_TUG + 0.12, H0 - shR + UP),       # the tug yanks his fist up
                  (T_GRAB, GRAB()), (T_GRAB + 0.25, GRAB() - Vector((0, 0, 0.008))),   # a beat frozen, reaching
                  (T_GRAB + 0.8, Vector((0.08, -0.15, -0.02))),                            # down in front of him, elbow low
                  (T_GRAB + 1.3, H0 - shR + Vector((-0.02, -0.02, 0.01)))])               # his empty fist, held where it was
    def hand(t):
        bpy.context.view_layer.update(); return acts._shoulder(data, R) + arc(t)
    reach(data, R, hand, 0.0, T_GRAB + 1.7, lead=0.05, back=1.0, elbow_out=0.35)   # the empty fist drops as he slumps
    data.look_at(KN0 + Vector((0, 0, 0.05)), 0.0, max_yaw=25, max_pitch=15, blend=0.0)
    data.look_at(kp(T_GRAB), T_SLIP + 0.05, max_yaw=25, max_pitch=16)       # the head tips a little; the eyes do the rest
    data.look_at(kp(T_GRAB + 0.6), T_GRAB + 0.2, max_yaw=25, max_pitch=18)
    data.look_at(H0 + Vector((-0.02, -0.02, 0.01)), T_GRAB + 1.1, max_yaw=25, max_pitch=30)   # a beat at his empty fist
    data.look_at(US, T_GRAB + 1.9, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_TUG)
    data.expression("alarmed", T_SLIP, T_GRAB + 0.9, blend=0.12)
    data.perform("sad", T_GRAB + 1.8, hold=max(0.6, DUR - T_GRAB - 2.5), arms=False)
    data.finish()
    soft_key("balloon key", (0.6, -1.0, 0.9), tuple(KN0 + Vector((0, 0, 0.1))), energy=20, size=40)
    C0, L0 = Vector((0.06, -1.1, 0.62)), Vector((0.06, 0.06, 0.68))   # a touch low, looking up a little: his face
    cam = K.camera(tuple(C0), tuple(L0), lens=27, fstop=4.0)          # stays ours while he looks up after it
    camera_path(cam, lambda t: (C0, L0, Vector((0.04, -0.05, 0.6))))
    return dict(**where, data=data, rest=1, grips=("escape",),
                conseq=[("the string slips out of his fist and the balloon rises away", lambda: meshes([b]) + [bpy.data.objects["escape string"]], T_SLIP, T_GRAB + 0.5,
                         {"whole": False, "moves": lambda: meshes([b])})])


# ================================================================ SHOT 4: the scanner
def shot4():
    """HE POURS FREEZING HELIUM INTO THE SCANNER. In the scanner room, on a steel cart right in front of Data, a
    model MRI: a fat white ring round a dark bore, its blue-padded bed sliding out toward us, a big red lamp on its
    face, a steel funnel on top. He tips a steel flask over the funnel; soft white freezing vapour pours down into it,
    frost creeps out over the ring from the port, and the lamp switches from red to green. He looks at us, impressed.
    (The life-size version: 38-72 over ten rounds, the ring never fitting in a phone frame beside him.)"""
    where = place("hospital")
    data = load_data(); data.place(-0.12, 0.0, 0)
    L, R = sides(data)
    top = counter("scanner cart", y=-0.22, w=0.8, d=0.26, h=0.17)    # a low cart: the funnel at his chest, in reach
    shR = acts._shoulder(data, R)
    SC = Vector((shR.x + 0.16, -0.16, top))                         # the hero: big, beside him, never in front of him
    ms = HK.model_scanner("model", tuple(SC), R=0.112, depth=0.13, light_r=0.036, shell_hex="#A9B5C2")   # blue-grey: the white frost shows on it
    ms["root"].rotation_euler = (0, 0, math.radians(24)); bpy.context.view_layer.update()   # three-quarter: the bore and the bed read (round 12: "a hair dryer")
    MW = ms["root"].matrix_world.copy()
    PORT = MW @ ms["port"]; JOINT = MW @ ms["joint"]
    fl, mouth_l = HK.dewar("flask", (0, 0, 0), r=0.038, h=0.13)
    HOLD = shR + Vector((0.03, -0.11, -0.12))
    POUR = PORT + Vector((-0.045, 0.02, 0.008))                    # the flask's middle beside the funnel, under his chin
    T_LIFT, T_TIP0, T_TIP1, T_BACK = 0.3, 1.1, DUR - 2.0, DUR - 0.5
    SET = POUR + Vector((-0.015, -0.02, -0.04))                     # set down low beside the ring, never back up past his face
    fp = spline([(0.0, HOLD), (T_LIFT, HOLD), (T_TIP0, POUR), (T_TIP1, POUR), (T_BACK, SET)])
    tip = lambda t: 1.65 * ease(min(1.0, max(0.0, (t - T_TIP0 + 0.3) / 0.5))) * (1 - ease(min(1.0, max(0.0, (t - T_TIP1) / 0.5))))
    follow(fl, fp, 0.0, DUR, rot_fn=lambda t: (0, tip(t), 0))
    def at(local):
        def fn(t):
            sc.frame_set(F(t)); bpy.context.view_layer.update(); return fl.matrix_world @ Vector(local)
        return fn
    mouth = at(mouth_l)
    puffs = HK.cold_smoke("cold", mouth, lambda t: PORT - mouth(t), T_TIP0 + 0.15, T_TIP1 - 0.2, NF, n=300, seed=4,
                          into=PORT + Vector((0, 0, -0.03)))
    HK.frost(ms["parts"], T_TIP0 + 0.3, T_TIP0 + 1.2)
    HK.frost_spread(ms["ring"], JOINT, T_TIP0 + 0.4, T_TIP1 + 0.3, 0.27)
    st = ms["light"]
    HK.status(st, 0.0, "#E01810", emit=3.0); HK.status(st, T_TIP1 - 0.3, "#E01810", emit=3.0)
    HK.status(st, T_TIP1 - 0.15, "#10D040", emit=5.0); HK.status(st, T_TIP1 + 0.25, "#10D040", emit=3.5)
    reach(data, R, at((-0.036, -0.008, 0.03)), 0.0, DUR, lead=0.05, back=None, elbow_out=0.5)   # his hand low on the flask's near side
    LAMP = MW @ Vector((0.112 * 0.62, -0.069, 0.128 + 0.112 * 0.62))
    data.look_at(fp(0.0) + Vector((0, 0, 0.06)), 0.0, max_yaw=30, max_pitch=30, blend=0.0)
    data.look_at(PORT, T_TIP0 - 0.2, max_yaw=35, max_pitch=30)
    data.look_at(LAMP, T_TIP1 - 0.4, max_yaw=40, max_pitch=25)
    data.look_at(US, T_TIP1 + 0.45, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("neutral", 0.3, T_TIP1 - 0.45)                     # focused, not cross (round 12: "brows angry")
    data.expression("surprised", T_TIP1 - 0.05, T_TIP1 + 0.5, blend=0.15)   # the lamp pops green, then his face
    data.expression("happy", T_TIP1 + 0.6, DUR + 1.0, blend=0.3)
    data.finish()
    soft_key("pour key", (-0.7, -1.0, 1.0), tuple(PORT + Vector((0, 0, 0.05))), energy=16, size=34)
    soft_key("scanner key", (0.9, -0.9, 1.2), tuple(SC + Vector((0, 0, 0.12))), energy=12, size=34, color=(0.92, 0.96, 1.0))
    C0, L0 = Vector((0.03, -1.1, 0.66)), Vector((0.03, 0.0, 0.54))
    C1, L1 = Vector((0.03, -1.02, 0.65)), Vector((0.03, 0.0, 0.54))
    cam = K.camera(tuple(C0), tuple(L0), lens=27, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.0, -0.12, 0.52))))
    return dict(**where, data=data, rest=1, grips=("flask", "model"),
                conseq=[("frost spreads over the ring and its lamp switches from red to green",
                         lambda: [bpy.data.objects[ms["ring"]], bpy.data.objects["model status light"]], T_TIP0 + 0.4, DUR, {"whole": False})])


# ================================================================ SHOT 5: payoff
def shot5():
    """WOULD YOU STILL BUY ONE? Back at the party counter: Data holds a pink balloon by its string down at his side
    (image-left), the balloon floating beside his head; on the counter at the image-right stands the little MRI from
    beat 4, frosted, its lamp green. He looks up at the balloon, then across to the scanner, then into the lens, one
    brow up, and lifts the balloon a little toward us. The question is the look and the offered balloon."""
    where = store_set()
    data = load_data(); data.place(0.04, 0.06, 0)
    L, R = sides(data)
    top = counter("party counter")
    shL, shR = acts._shoulder(data, L), acts._shoulder(data, R)
    SC = Vector((shR.x + 0.135, -0.21, top))                        # at the image-right, clear of his arm and body
    ms = HK.model_scanner("model", tuple(SC), R=0.085, depth=0.11, light_r=0.03, shell_hex="#A9B5C2")
    HK.status(ms["light"], 0.0, "#10D040", emit=3.5)
    HK.frost(ms["parts"], 0.0, 0.01)
    HK.frost_spread(ms["ring"], SC + ms["joint"], 0.0, 0.05, 0.3)
    H0 = shL + Vector((-0.07, -0.08, -0.09))                       # his fist low at his side
    # THE WEIGHING (round 12: "a held pose ... the lift is a few pixels"): he looks up at the balloon, presents the
    # frosted scanner with his other hand, then holds the two out like the pans of a scale and weighs them, the
    # balloon side and the scanner side bobbing against each other to the last frame, brow up at us: which one?
    T_LOOK_B, T_LOOK_S, T_LOOK_US, T_OFFER0, T_OFFER1, T_WEIGH = 0.15, 1.35, 2.7, 2.8, 3.6, 3.7
    H1 = shL + Vector((-0.06, -0.15, -0.05))                       # held out toward us, still low and wide
    weigh = lambda t, ph: 0.024 * math.sin(2 * math.pi * (t - T_WEIGH) / 1.3 + ph) * ease(min(1.0, max(0.0, (t - T_WEIGH) / 0.5)))
    Hs = spline([(0.0, H0), (T_OFFER0, H0), (T_OFFER1, H1)])
    H = lambda t: Hs(t) + Vector((0, 0, weigh(t, 0.0)))
    reach(data, L, H, 0.0, DUR, lead=0.05, back=None, elbow_out=0.45)
    PR0 = shR + Vector((0.07, -0.12, 0.02))                        # his right hand up over the scanner, presenting it
    PR = lambda t: PR0 + Vector((0, 0, weigh(t, math.pi)))
    reach(data, R, PR, T_LOOK_S + 0.25, DUR, lead=1.05, back=None, elbow_out=0.3)
    U = Vector((-0.09, -0.02, 0.25))                               # the balloon up and out beside his head
    b = HK.balloon("last balloon", (0, 0, 0), r=0.08, color="#E2559B")
    kp = lambda t: H(t) + U + bob(t, 2, amp=0.01)
    follow(b, kp, 0.0, DUR)
    HK.string_between("last string", H, kp, NF, r=0.0022)
    LAMP = SC + Vector((0.085 * 0.62, -0.06, 0.101 + 0.085 * 0.62))
    for k in range(2):                                             # the lamp blinks as he turns to it
        t = T_LOOK_S + 0.15 + k * 0.3
        HK.status(ms["light"], t, "#10D040", emit=3.5); HK.status(ms["light"], t + 0.12, "#40FF70", emit=9.0); HK.status(ms["light"], t + 0.26, "#10D040", emit=3.5)
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(kp(T_LOOK_B + 0.3) + Vector((0, 0, 0.03)), T_LOOK_B, max_yaw=40, max_pitch=32)
    data.look_at(LAMP, T_LOOK_S, max_yaw=45, max_pitch=25)
    data.look_at(US, T_LOOK_US, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.0, T_LOOK_S)
    data.expression("worried", T_LOOK_S + 0.15, T_LOOK_US)
    data.expression("wry", T_LOOK_US + 0.05, DUR + 1.0, blend=0.2)        # brow up at us; his hands do the body acting
    data.finish()
    soft_key("counter key", (0.6, -1.0, 1.0), tuple(SC + Vector((-0.1, 0, 0.15))), energy=18, size=40)
    C0, L0 = Vector((0.04, -1.02, 0.7)), Vector((0.04, 0.06, 0.6))   # waist-up: his face, the balloon and the scanner fill it
    C1, L1 = Vector((0.04, -0.96, 0.69)), Vector((0.04, 0.06, 0.6))
    cam = K.camera(tuple(C0), tuple(L0), lens=24, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), L0.lerp(L1, ease(t / DUR)), Vector((0.0, -0.08, 0.6))))
    return dict(**where, data=data, rest=1, grips=("last",),
                conseq=[("he lifts the balloon toward us, one brow up: would you?", lambda: meshes([b]), T_OFFER0, DUR, {"whole": False})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
