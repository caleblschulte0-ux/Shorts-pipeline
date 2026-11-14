"""THE SAFFRON SHORT (the third 3D short, 2026-11-13): saffron costs more than any spice on Earth, and it's all picked
by hand. Made end to end without a sign-off (caaleb, 2026-11-13: "start on a new video really hoping you can do one fast
with out me having to get invloved"), each beat its own place and its own idea (script.json `sets`, `ideas`).

  1 hook     store         a pile of cash for one tiny jar: he holds the jar up to us, sets it on the table and
                           shoves brick after brick of banknotes across to it.
  2 threads  crocus_field  one flower gives up just three red threads: he pulls them out one by one and holds
                           the three up to us, fanned in his fingers.
  3 by hand  sorting_room  the clock spins through the hours as he plucks: flower after flower, thread after thread,
                           the clock racing and the window going from day to night.
  4 the race crocus_field  the rising sun closes the flowers toward him: dawn opens the field, then the flowers start
                           folding shut, far to near, while he hurries with his basket.
  5 payoff   store         the tiny jar balances a heap of flowers: he tips a whole basket onto a balance against the
                           little jar and only then does it level; he holds up his own two hands.

Run through the shot harness (store/shots.py, STORY=saffron). The props are store/saffron_kit.py."""
import saffron_kit as SK
import prop_kit as PK
import produce as PR
import locations as LOC
from mathutils import Euler

TABLE = Vector((0.0, -0.32, 0.0))
TABLE_H = 0.32


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
    """one hand does a job: relaxed, swings onto the moving point fn(t) from t0 to t1, falls back relaxed"""
    bones = (f"arm.{side}", f"fore.{side}", f"hand.{side}")
    for b in bones:
        if not data._has_keys(data.arm, f'pose.bones["{b}"].rotation_euler'): data._k(b, 0.0, rot=data.RELAXED[b])
        data._k(b, max(0.0, t0 - lead), rot=data._pose_now(b, max(0.0, t0 - lead)) if t0 - lead > 0.05 else data.RELAXED[b])
    for f in range(F(t0), F(t1) + 1):
        t = (f - 1) / FPS; sc.frame_set(f); data._arm_ik(side, Vector(fn(t)), t, elbow_out)
    if back is not None:
        for b in bones: data._k(b, t1 + back, rot=data.RELAXED[b])


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


def head_pt(data, t):
    sc.frame_set(F(t)); bpy.context.view_layer.update()
    return data.arm.matrix_world @ data.pb["head"].head


# ================================================================ SHOT 1: the hook
def shot1():
    """A PILE OF CASH FOR ONE TINY JAR. Medium close at a low table in the store. He holds one little jar of red
    threads up beside his face to us, sets it on the table, then shoves a fat brick of banknotes across to it, and a
    second: the tiny jar against a heap of money. He looks back at us, eyebrows up."""
    where = store_set()
    SK.table("spice table", tuple(TABLE), w=0.9, d=0.42, h=TABLE_H)
    TOP = TABLE_H
    T_UP, T_DOWN0, T_DOWN1 = 0.0, 1.35, 1.85
    P1 = [(2.0, 2.6), (3.15, 3.75)]          # the two shoves
    J_REST = Vector((-0.17, -0.3, TOP))
    jar = SK.jar("jar", tuple(J_REST), h=0.095, r=0.032)     # small, but big enough to read as a jar of red on a phone
    data = load_data(); data.place(0.0, 0.08, 0)
    L, R = sides(data)
    sh = {s: acts._shoulder(data, s) for s in "LR"}
    UP = sh[L] + Vector((-0.05, -0.27, 0.1))
    jp = path([(0.0, UP), (T_DOWN0, UP + Vector((0.01, 0.0, 0.01))), (T_DOWN1, J_REST)])
    follow(jar, jp, 0.0, DUR)
    reach(data, L, lambda t: jp(t) + Vector((0.0, 0.0, 0.04)), 0.0, T_DOWN1 + 0.1, lead=0.05, back=0.4, elbow_out=0.35)
    # the cash: two bricks of 3 x 2 stacks, two layers high, shoved in from the right
    import props
    bill = props.bill_mesh("cash bill", w=0.1, h=0.045)
    bricks = []
    for k, (y, z) in enumerate(((-0.31, 0.0), (-0.31, 0.0))):
        root = K.empty(f"cash brick {k}", (0, 0, 0))
        for i in range(3):
            for j in range(2):
                for lay in range(2):
                    SK.cash_stack(f"cash {k}{i}{j}{lay}", (i * 0.046 - 0.046, j * 0.102 - 0.051, lay * 0.05), n=38, yaw=math.pi / 2, mesh=bill, seed=k * 9 + i * 3 + j, parent=root)
        bricks.append(root)
    B_START = [Vector((0.36, -0.3, TOP)), Vector((0.36, -0.3, TOP))]
    B_END = [Vector((-0.03, -0.3, TOP)), Vector((0.13, -0.3, TOP))]
    for k, root in enumerate(bricks):
        (a, b) = P1[k]
        start = B_START[k] if k == 0 else Vector((0.36, -0.3, TOP))
        bp = path([(0.0, start), (a, start), (b, B_END[k])])     # side by side on the table: a wide heap of money
        follow(root, bp, 0.0, DUR)
        root.scale = (0.0, 0.0, 0.0) if k else (1, 1, 1)
        if k:
            root.keyframe_insert("scale", frame=1); root.scale = (0, 0, 0); root.keyframe_insert("scale", frame=F(a - 0.4))
            root.scale = (1, 1, 1); root.keyframe_insert("scale", frame=F(a - 0.15))
        reach(data, R, lambda t, bp=bp: bp(t) + Vector((0.075, 0.0, 0.045 + (0.05 if k == 0 else 0.0))), a - 0.05, b + 0.05, lead=0.35 if k == 0 else 0.4,
              back=0.4 if k == 1 else None, elbow_out=0.4)
    US = Vector((0.0, -1.3, 0.62))
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(jp(T_DOWN1) + Vector((0, 0, 0.03)), T_DOWN0 + 0.1, max_yaw=30, max_pitch=22)   # head only: the neck bend put his forearm in his head
    data.look_at(B_END[0] + Vector((0, 0, 0.1)), P1[0][0] + 0.2, max_yaw=30)
    data.look_at(US, P1[1][1] + 0.15, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("pleased", 0.05, T_DOWN0)
    data.expression("determined", P1[0][0] - 0.1, P1[1][1])
    tr = data.perform("surprised", P1[1][1] + 0.1, hold=max(0.4, DUR - P1[1][1] - 0.6), arms=False)
    data.blink(0.9)
    data.finish()
    soft_key("table key", (0.5, -1.0, 1.0), (0.0, -0.3, TOP + 0.05), energy=22, size=30)
    C0, C1 = Vector((-0.08, -0.82, 0.66)), Vector((0.0, -1.15, 0.86))   # close on the jar first: it has to read as red
    L0, L1 = Vector((-0.06, -0.1, 0.6)), Vector((0.0, -0.12, 0.4))
    cam = K.camera(tuple(C0), tuple(L0), lens=32, fstop=4.0)
    cp = lambda t: (C0.lerp(C1, ease(min(1.0, max(0.0, (t - 1.2) / 1.0)))), L0.lerp(L1, ease(min(1.0, max(0.0, (t - 1.2) / 1.0)))), Vector((0.0, -0.2, 0.5)))
    camera_path(cam, cp)
    return dict(**where, data=data, rest=1, grips=("jar", "cash"),
                conseq=[("he holds the tiny jar up to us", lambda: meshes([jar]), 0.0, T_DOWN0),
                        ("the cash piles up beside the tiny jar", lambda: meshes(bricks), P1[0][0], DUR)])


# ================================================================ SHOT 2: three threads
def shot2():
    """THREE THREADS FROM ONE FLOWER. Waist-up in the field, the framing that passed for shot 4: Data holds ONE crocus
    up in front of his chest and, with his other hand, pulls its three red threads out one at a time, each up into
    clear air, keeping them fanned in his fingers; he ends holding up the three, the flower empty, and looks at us.
    (2026-11-14: nine rounds on a scale needle, then three on a giant crocus his short arms could not reach without
    every frame fighting the rig. The simplest picture of the line, in the layout the panel already passes.)"""
    where = place("crocus_field")
    data = load_data(); data.place(0.08, 0.05, 0)
    L, R = sides(data)
    shL, shR = acts._shoulder(data, L), acts._shoulder(data, R)          # his arms reach 0.19 m: everything sits inside that
    G = Vector((data.pos().x + 0.03, shR.y - 0.15, 0.38))                # his grip on the stem, in front of his chest
    SC = 1.5
    hm = SK.crocus_mesh("held crocus", seed=61, threads=False)
    hero = bpy.data.objects.new("held crocus", hm); bpy.context.collection.objects.link(hero)
    HROT = Euler((math.radians(-38), 0, 0.6))                          # tipped toward us: you see into the cup
    hero.location = G - Vector((0, 0, 0.015)); hero.rotation_euler = HROT; hero.scale = (SC, SC, SC)
    CUP = hero.location + HROT.to_matrix() @ Vector((0, 0, 0.16 * 0.38 * SC + 0.004))
    th_m = SK._mat("held thread", SK.THREAD, rough=0.6)
    TL, TR = 0.1, 0.0085                              # thick enough to read as red at phone size
    threads = []
    for k in range(3):
        root = K.empty(f"thread {k}", (0, 0, 0))
        pts = [Vector(((0.006 if k % 2 else -0.006) * math.sin(math.pi * v), 0, TL * v)) for v in (0.0, 0.35, 0.7, 0.9)]
        for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
            K.capsule(f"thread {k} seg {i}", p0, p1, TR, th_m, parent=root, seg=10, ra=TR * (0.75 + 0.1 * i), rb=TR * (0.85 + 0.1 * i))
        K.capsule(f"thread {k} tip", pts[-1], Vector((0, 0, TL + 0.012)), TR, th_m, parent=root, seg=12, ra=TR * 1.1, rb=TR * 1.25)
        a = math.radians(120 * k + 50); sp = math.radians(32)
        d = HROT.to_matrix() @ Vector((math.cos(a) * math.sin(sp), math.sin(a) * math.sin(sp), math.cos(sp)))
        threads.append(dict(root=root, rest_rot=d.to_track_quat('Z', 'Y').to_euler()))
    BEATS = [0.9, 2.6, 4.3]                          # reach the cup; pinch; pull up and out by +0.75; held
    HOLD = shL + Vector((-0.13, -0.09, 0.04))
    VIA = shL + Vector((-0.1, -0.11, -0.04))         # out in front first, so his forearm never sweeps past his chin           # up beside him, against the sky, clear of his face
    REST = shL + Vector((-0.06, -0.08, -0.1))
    def lhand(t):
        if t < BEATS[0] - 0.75: return REST
        for k, g in enumerate(BEATS):
            tip = CUP + Vector((-0.01, -0.01, 0.03))        # his fingers pinch at the heart of the cup, where the threads start
            prev = REST if k == 0 else HOLD
            if t < g:
                if t <= g - 0.75: return prev
                u = (t - (g - 0.75)) / 0.75
                return prev.lerp(VIA, ease(u / 0.5)) if u < 0.5 else VIA.lerp(tip, ease((u - 0.5) / 0.5))
            if t < g + 0.2: return tip
            if t < g + 0.7: return tip.lerp(VIA, ease((t - g - 0.2) / 0.5))
            if t < g + 1.15: return VIA.lerp(HOLD, ease((t - g - 0.7) / 0.45))
            if k == 2 or t < BEATS[k + 1] - 0.45: 
                if k == 2: return HOLD
                return HOLD
        return HOLD
    def trot(k, t):
        g = BEATS[k]
        if t < g + 0.2: return threads[k]["rest_rot"]
        u = ease(min(1.0, (t - g - 0.2) / 0.5))
        r0 = threads[k]["rest_rot"]; fan = (k - 1) * 0.3
        return Euler((r0.x * (1 - u), r0.y * (1 - u) + fan * u, r0.z * (1 - u)))
    US = Vector((0.0, -1.3, 0.62))
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    for k, g in enumerate(BEATS):
        data.look_at(CUP, g - 0.35, max_yaw=30, max_pitch=30)
        data.look_at(HOLD + Vector((0, 0, 0.06)), g + 0.6, max_yaw=35)        # eyes on the thread as it comes up
    data.look_at(US, BEATS[2] + 1.3, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, BEATS[2] + 1.1)
    data.expression("surprised", BEATS[2] + 1.3, DUR + 1.0, blend=0.15)
    data.blink(1.6); data.blink(3.3)
    reach(data, R, lambda t: G, 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    reach(data, L, lhand, 0.0, DUR, lead=0.05, back=None, elbow_out=0.25)
    data.finish()
    def hand_at(side, t):                             # the threads ride his REAL hand, wherever the solve put it
        sc.frame_set(F(t)); bpy.context.view_layer.update(); return data.arm.matrix_world @ data.pb[f"hand.{side}"].tail
    def tpos(k, t):
        g = BEATS[k]
        if t < g + 0.2: return CUP
        return hand_at(L, t) + Vector(((k - 1) * 0.01, -0.005, -0.006))
    follow(hero, lambda t: hand_at(R, t) - Vector((0, 0, 0.03)), 0.0, DUR, rot_fn=lambda t: tuple(HROT))   # the flower is IN his fist, wherever the solve put it
    for k, th in enumerate(threads):
        follow(th["root"], lambda t, k=k: tpos(k, t), 0.0, DUR, rot_fn=lambda t, k=k: trot(k, t))
    soft_key("thread key", (0.5, -1.1, 0.85), tuple(CUP), energy=10, size=30)
    C0, L0 = Vector((0.0, -1.02, 0.52)), Vector((0.0, 0.2, 0.52))     # a real waist-up (45 mm): legs out of frame, the fanned threads inside it
    C1, L1 = Vector((0.0, -0.97, 0.52)), Vector((0.0, 0.2, 0.52))
    cam = K.camera(tuple(C0), tuple(L0), lens=45, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((0.0, 0.0, 0.5))))
    one = lambda k: (lambda: meshes([threads[k]["root"]]))
    return dict(**where, data=data, rest=1, grips=("held crocus", "thread 0", "thread 1", "thread 2"),
                conseq=[("the first red thread comes up out of the flower", one(0), BEATS[0] + 0.2, BEATS[1]),
                        ("the second joins it", lambda: meshes([threads[0]["root"], threads[1]["root"]]), BEATS[1] + 0.2, BEATS[2]),
                        ("all three held up, the flower empty", lambda: meshes([t_["root"] for t_ in threads] + [hero]), BEATS[2] + 0.2, DUR)])


# ================================================================ SHOT 3: by hand, for hours
def shot3():
    """THE CLOCK SPINS THROUGH THE HOURS AS HE PLUCKS. A farmhouse table heaped with crocuses; he takes a flower in one
    hand and pulls its threads into a little dish with the other, again and again, faster and faster, the spent
    flowers piling up on his right; behind him the wall clock races and the window goes from day to night."""
    where = place("sorting_room")
    TB = Vector((0.0, -0.3, 0.0)); TH = 0.36; TOP = TH + 0.0
    SK.table("sorting table", tuple(TB), w=0.95, d=0.42, h=TH)
    HEAP = Vector((-0.27, -0.33, TOP)); DISH = Vector((0.0, -0.4, TOP)); SPENT = Vector((0.16, -0.36, TOP))
    K.cyl("dish", (DISH.x, DISH.y, TOP + 0.008), 0.05, 0.016, K.mat("dish", "#F1ECE2", rough=0.3), bev=0.004)
    rnd = random.Random(9)
    heap = []
    for i in range(34):
        a = rnd.uniform(0, 6.28); rr = rnd.uniform(0, 0.11); z = TOP + 0.005 + max(0.0, 0.07 * (1 - rr / 0.12)) * rnd.uniform(0.3, 1.0)
        o = SK.crocus(f"heap flower {i}", (HEAP.x + math.cos(a) * rr, HEAP.y + math.sin(a) * rr * 0.8, z), seed=700 + i, own=False,
                      mesh=bpy.data.meshes.get(f"crocus tmpl {i % 5}") or SK.crocus_mesh(f"crocus tmpl {i % 5}", seed=100 + i % 5))
        o.rotation_euler = (rnd.uniform(-1.4, 1.4), rnd.uniform(-1.4, 1.4), rnd.uniform(0, 6.28)); heap.append(o)
    clock, hh, mm = SK.wall_clock("wall clock", (0.62, 0.66, 1.0), r=0.15)
    T_END = DUR - 0.25
    SK.spin_clock(hh, mm, 0.15, T_END, hours=9.0, start_h=7.0)
    sun, lamp = LOC.WINDOW_SUN, LOC.WINDOW_LAMP
    skym = bpy.data.materials["window sky"].node_tree.nodes["Principled BSDF"]
    for t_, e_, c_, s_, l_ in ((0.0, 260, (1.0, 0.92, 0.8), 2.0, 0.0), (T_END * 0.55, 200, (1.0, 0.7, 0.45), 1.2, 0.0), (T_END * 0.8, 40, (0.5, 0.55, 0.9), 0.25, 8.0), (T_END, 6, (0.35, 0.4, 0.8), 0.05, 14.0)):
        sun.data.energy = e_; sun.data.keyframe_insert("energy", frame=F(t_)); sun.data.color = c_; sun.data.keyframe_insert("color", frame=F(t_))
        skym.inputs["Emission Strength"].default_value = s_; skym.inputs["Emission Strength"].keyframe_insert("default_value", frame=F(t_))
        lamp.data.energy = l_; lamp.data.keyframe_insert("energy", frame=F(t_))
    K.cyl("oil lamp base", (0.55, -0.15, TOP + 0.03), 0.03, 0.06, K.mat("lamp brass", "#B8893A", rough=0.3, metal=0.9), bev=0.004)
    K.sph("oil lamp glass", (0.55, -0.15, TOP + 0.1), 0.035, K.mat("lamp glass", "#FFD9A0", rough=0.1, emit=0.0), scale=(1, 1, 1.3))
    data = load_data(); data.place(0.0, 0.1, 0)
    L, R = sides(data)
    # the plucking: cycles that get faster (the time-lapse), each: L takes a flower from the heap to the middle, R pulls
    # its threads into the dish; the spent flower is dropped on the pile to his right
    cyc, t = [], 0.35; per = 0.95
    while t + per < T_END - 0.1:
        cyc.append((t, per)); t += per; per = max(0.42, per * 0.8)
    MID = Vector((-0.05, -0.36, TOP + 0.13))
    def lhand(t):
        for t0, p in cyc:
            if t0 <= t < t0 + p:
                u = (t - t0) / p
                a, b = HEAP + Vector((0.02, 0.0, 0.09)), MID
                if u < 0.35: return a.lerp(b, ease(u / 0.35)) + Vector((0, 0, 0.04 * math.sin(math.pi * u / 0.35)))
                if u < 0.7: return b
                return b.lerp(a, ease((u - 0.7) / 0.3))
        return HEAP + Vector((0.02, 0.0, 0.09))
    def rhand(t):
        for t0, p in cyc:
            if t0 <= t < t0 + p:
                u = (t - t0) / p
                a, b = MID + Vector((0.06, -0.01, 0.04)), DISH + Vector((0.02, 0.0, 0.07))
                if u < 0.3: return b.lerp(a, ease(u / 0.3))
                if u < 0.45: return a
                return a.lerp(b, ease(min(1.0, (u - 0.45) / 0.35)))
        return DISH + Vector((0.02, 0.0, 0.07))
    reach(data, L, lhand, 0.25, T_END, lead=0.25, back=0.4, elbow_out=0.45)
    reach(data, R, rhand, 0.25, T_END, lead=0.25, back=0.4, elbow_out=0.45)
    # each cycle: a flower rides his left hand from the heap to the middle, then lands on the spent pile; three red
    # threads appear in the dish
    tm = [bpy.data.meshes.get(f"crocus tmpl {k}") for k in range(5)]
    thm = SK._mat("crocus thread", SK.THREAD, rough=0.35)
    spent = []
    for i, (t0, p) in enumerate(cyc):
        o = SK.crocus(f"in hand {i}", tuple(HEAP), seed=900 + i, own=False, mesh=tm[i % 5]); o.scale = (0, 0, 0)
        land = SPENT + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0.01 + 0.012 * i))
        def pos(t, t0=t0, p=p, land=land):
            if t < t0 + 0.7 * p: return lhand(t) + Vector((0.0, 0.0, -0.02))
            u = min(1.0, (t - t0 - 0.7 * p) / (0.3 * p)); return (MID + Vector((0, 0, -0.02))).lerp(land, ease(u)) + Vector((0, 0, 0.035 * math.sin(math.pi * u)))
        yaw_ = rnd.uniform(0, 6.28)     # it tips over as it drops and LIES on the pile (the judge: "standing upright on their stems")
        follow(o, pos, t0, DUR, rot_fn=lambda t, t0=t0, p=p, yaw_=yaw_: (0.4 + 1.15 * ease(min(1.0, max(0.0, (t - t0 - 0.7 * p) / (0.3 * p)))), 0.2, yaw_))
        for t_, s_ in ((0.0, 0), (t0 - 0.01, 0), (t0 + 0.08, 1.0)): o.scale = (s_, s_, s_); o.keyframe_insert("scale", frame=max(1, F(t_)))
        o.location = HEAP; o.keyframe_insert("location", frame=1)
        spent.append(o)
        for k in range(3):   # its threads in the dish
            a = rnd.uniform(0, 6.28); r_ = rnd.uniform(0, 0.03)
            c = K.cyl(f"dish thread {i}{k}", (DISH.x + math.cos(a) * r_, DISH.y + math.sin(a) * r_, TOP + 0.018 + 0.002 * i), 0.0028, 0.035, thm, rot=(math.pi / 2, 0, rnd.uniform(0, 6.28)), v=6, bev=0)
            ta = t0 + 0.75 * p
            for t_, s_ in ((0.0, 0), (ta, 0), (ta + 0.05, 1)): c.scale = (s_, s_, s_); c.keyframe_insert("scale", frame=max(1, F(t_)))
        if i < len(heap): hide_from(heap[-1 - i], t0 + 0.05)
    data.look_at(MID + Vector((0, 0, -0.02)), 0.0, max_yaw=25, blend=0.0)
    data.look_at(Vector((0.0, -1.3, 0.6)), T_END - 0.5, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.0, T_END * 0.5)
    data.expression("worried", T_END * 0.5, DUR)
    for k_, (t0, p) in enumerate(cyc):     # his head goes with each flower: down to the dish, up to the next
        data._k("neck", t0 + 0.2 * p, rot=(6, 4, 0)); data._k("neck", t0 + 0.6 * p, rot=(9, -5, 0))
    data.blink(0.6)
    data.finish()
    soft_key("table key", (-0.6, -0.9, 1.1), (0.0, -0.33, TOP), energy=20, size=40)
    C0, L0 = Vector((-0.2, -1.2, 0.72)), Vector((0.02, -0.05, 0.55))
    C1, L1 = Vector((-0.15, -1.1, 0.7)), Vector((0.06, -0.05, 0.56))
    cam = K.camera(tuple(C0), tuple(L0), lens=28, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((0.0, -0.2, 0.55))))
    return dict(**where, data=data, rest=1, grips=("in hand",),
                conseq=[("flower after flower goes from the heap to the spent pile, its threads into the dish", lambda: meshes(spent), cyc[0][0] + 0.3, T_END),
                        ("the clock races through the hours", lambda: meshes([clock]), 0.3, T_END)])


# ================================================================ SHOT 4: the race
def shot4():
    """IT'S A RACE. Dawn in the field: Data holds a ringing alarm clock up to us, its hands racing, while the crocus in
    his other hand wilts brown and flops over and the field behind him shuts. He looks down at it, then at us, alarmed."""
    where = place("crocus_field")
    own = list(LOC.FIELD_OWN)
    T_SHUT0, T_SHUT1 = 0.7, DUR - 0.9
    for o in own:
        y = o.location.y; kb = o.data.shape_keys.key_blocks["closed"]
        c_at = (T_SHUT1 - 1.6) + 1.2 * max(0.0, min(1.0, (2.2 - y) / 3.2))   # then the field: a quick wave of shutting rolling at him
        for t_, v in ((0.0, 0.0), (c_at, 0.0), (c_at + 0.9, 1.0)):     # wide open at first; one change only: they shut
            kb.value = v; kb.keyframe_insert("value", frame=F(min(DUR, t_)))
    # no sun disc: four rounds read it as a flat lamp or a moon; the dawn light warming over the shot carries it
    def light():
        key = LOC.sky_light(sun_elev=6, sun_az=160, sun=2.6, sky=0.18, warm=(1.0, 0.62, 0.36), haze=1.4)
        sun = next(o for o in bpy.data.objects if o.type == 'LIGHT' and o.data.type == 'SUN')
        r0 = sun.rotation_euler.copy()
        for t_, el, en in ((0.0, 2, 0.6), (DUR, 14, 3.2)):
            sun.rotation_euler = (math.radians(90 - el), r0.y, r0.z); sun.keyframe_insert("rotation_euler", frame=F(t_))
            sun.data.energy = en; sun.data.keyframe_insert("energy", frame=F(t_))
        return key
    where["light"] = light
    data = load_data(); data.place(0.08, 0.05, 0)
    L, R = sides(data)
    # 2026-11-14 rethink (operator: "90 degrees didn't work 3 times, try 180"): six rounds asked his FACE to carry the
    # race and the flowers to read from a petal fold. Now two props carry it: a ringing alarm clock held up to us,
    # its hands racing, and the crocus in his other hand wilting brown and drooping. Neither needs a subtle face.
    shL4, shR4 = acts._shoulder(data, L), acts._shoulder(data, R)
    G = shR4 + Vector((0.08, -0.12, 0.0))                            # out to his side, against the field, not his coat                           # inside his 0.19 m reach: no clamped, floating hand                    # his grip on the stem, in front of his chest
    hero = SK.crocus("dawn crocus", (0, 0, 0), yaw=0.6, scale=1.6, seed=61)
    T_W0, T_W1 = 0.6, DUR - 0.8
    droop = PK.wilt(hero, T_W0, T_W1, brown="#3A2212", to=1.0, slots=(0,))   # a deep brown: dull maroon read as purple      # this one flower browns, shuts and droops (the shared prop kit)
    follow(hero, lambda t: G - Vector((0, 0, 0.05)), 0.0, DUR, rot_fn=lambda t: (-droop(t), 0, 0.6))   # it flops over toward us
    # the alarm clock, held up beside his face: bells on top, hands racing, ringing (a fast shake)
    CK = shL4 + Vector((-0.04, -0.15, 0.0))            # where his hand really is, at chest height: face stays clear
    ak = PK.alarm_clock("alarm clock", r=0.075); clock = ak["root"]
    ak["race"](0.2, DUR - 0.3, hours=5.0, start_h=5.0)
    buzz = lambda t: Vector((0.008 * math.sin(2 * math.pi * 13 * t), 0, 0.006 * math.sin(2 * math.pi * 17 * t + 1.0))) * (1.0 if t > 0.4 else t / 0.4)
    follow(clock, lambda t: CK + buzz(t), 0.0, DUR, rot_fn=lambda t: (0, PK.ring(t, amp_deg=22.0), 0))   # it RINGS: a hard rattle you can see
    US = Vector((0.0, -1.3, 0.62))
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)                       # to us, with the clock: "it's a race"
    data.look_at(G + Vector((0, 0, 0.08)), 1.2, max_yaw=10, max_pitch=40)   # down at the flower as it wilts
    data.gaze(1.2, 0, -22); data.gaze(T_W1 - 0.5, 0, -22)
    data.look_at(US, T_W1 - 0.4, max_yaw=20)                           # back to us
    data.gaze(T_W1 - 0.3, 0, 0, blend=0.1)
    data.idle(0.0, DUR)
    data.expression("worried", 0.0, T_W1 - 0.45, blend=0.3)
    data.perform("alarmed", T_W1 - 0.4, hold=DUR, arms=False, pace=0.55)
    data.expression("alarmed", T_W1 - 0.3, DUR + 1.0, blend=0.12)
    data.blink(0.9)
    # hands solved AFTER the body acts, so his recoil does not carry them off the props
    reach(data, R, lambda t: G + Vector((0.0, 0.0, 0.004 * math.sin(2.0 * t))), 0.0, DUR, lead=0.05, back=None, elbow_out=0.4)
    reach(data, L, lambda t: CK + buzz(t) + Vector((0.02, 0.025, -0.075)), 0.0, DUR, lead=0.05, back=None, elbow_out=0.45)   # his hand under the clock, holding it up
    data.finish()
    def hand_at(side, t):                              # the props ride his REAL hands, wherever the solve put them
        sc.frame_set(F(t)); bpy.context.view_layer.update(); return data.arm.matrix_world @ data.pb[f"hand.{side}"].tail
    follow(clock, lambda t: hand_at(L, t) + Vector((-0.02, -0.025, 0.075)) + buzz(t), 0.0, DUR, rot_fn=lambda t: (0, PK.ring(t, amp_deg=22.0), 0))
    follow(hero, lambda t: hand_at(R, t) - Vector((0, 0, 0.05)), 0.0, DUR, rot_fn=lambda t: (-droop(t), 0, 0.6))
    soft_key("rim fill", (0.5, -1.1, 0.8), (0.0, 0.0, 0.5), energy=9, size=40, color=(1.0, 0.8, 0.65))
    C0, L0 = Vector((0.08, -1.12, 0.52)), Vector((0.08, 0.2, 0.52))    # waist-up (45 mm): clock left, flower right, face clear between
    C1, L1 = Vector((0.08, -1.07, 0.52)), Vector((0.08, 0.2, 0.52))
    cam = K.camera(tuple(C0), tuple(L0), lens=45, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, t / DUR), L0.lerp(L1, t / DUR), Vector((0.0, 0.0, 0.5))))
    return dict(**where, data=data, rest=1, grips=("dawn crocus", "alarm clock"),
                conseq=[("the alarm clock rings, its hands racing", lambda: meshes([clock]), 0.3, DUR),
                        ("the crocus in his hand wilts brown and droops", lambda: [hero], T_W0, DUR),
                        ("the field folds shut behind him", lambda: own, 0.2, DUR, {"whole": False})])


# ================================================================ SHOT 5: the payoff
def shot5():
    """THE TINY JAR BALANCES A HEAP OF FLOWERS. Close on the store table: a big brass balance stands right in front
    of Data, the tiny jar alone on its left pan, which sits low. He tips his basket over the right pan and a stream of
    flowers falls onto it, heaping, and only then does the beam come level. He sets the empty basket down and holds
    his open hand up to us, grinning. (Rethought 2026-11-13: in a wide shot the beam was a thread and the pour hid
    in the basket. Now the balance is big and in front of him, and the camera is close.)"""
    where = store_set()
    SK.table("spice table", tuple(TABLE), w=0.9, d=0.42, h=TABLE_H)
    TOP = TABLE_H
    S = 1.7                                       # the balance, scaled up to read on a phone
    ARM, BH, PR_ = 0.13, 0.14, 0.07               # local sizes: a tall post, so the low pan hangs clearly in the air
    BC = Vector((-0.05, -0.3, TOP))     # left of centre: the heaped right pan sits well inside the frame
    bal, beam, pans = SK.balance("balance", tuple(BC), arm=ARM, h=BH, pan_r=PR_)
    bal.scale = (S, S, S)
    DROP = BH * 0.62 * S
    T_LIFT, T_TIP1, T_POUR0, T_POUR1 = 0.4, 1.1, 1.15, 2.9
    TILT0 = math.radians(22)                     # the jar side sits down
    def tilt(t):
        # it holds DOWN through most of the pour, then comes level in one move, wobbles, and stops: "only then"
        T_LV = T_POUR1 - 0.45
        if t < T_LV: return -TILT0 * (1 - 0.12 * ease(max(0.0, (t - T_POUR0) / (T_LV - T_POUR0))))
        u = min(1.0, (t - T_LV) / 0.45); base = -TILT0 * 0.88 * (1 - ease(u))
        w = max(0.0, t - T_LV - 0.45)
        return base + (math.radians(7) * math.exp(-3.5 * w) * math.sin(8 * w) if t > T_LV + 0.45 else 0.0)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; beam.rotation_euler = (0, tilt(t), 0); beam.keyframe_insert("rotation_euler", frame=f)
    SK.level_pans(beam, pans, NF)
    def pan_pt(sg, t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return (beam.matrix_world @ Vector((sg * ARM, 0, 0))) - Vector((0, 0, DROP - 0.006 * S))
    jar = SK.jar("jar", tuple(pan_pt(-1, 0.0)), h=0.12, r=0.04)     # bigger here: it has to read against the heap
    follow(jar, lambda t: pan_pt(-1, t), 0.0, DUR)
    data = load_data(); data.place(0.0, 0.08, 0)
    L, R = sides(data)
    sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
    bk = SK.basket("pour basket", (0, 0, 0), r=0.09, h=0.075)
    for k in range(10):    # it starts full: flowers you can see over its rim
        rnd0 = random.Random(70 + k); a_ = rnd0.uniform(0, 6.28); rr = rnd0.uniform(0, 0.06)
        o = SK.crocus(f"basket top {k}", (math.cos(a_) * rr, math.sin(a_) * rr, 0.06), seed=700 + k, scale=0.55, own=False, mesh=bpy.data.meshes.get(f"crocus tmpl {k % 5}"))
        o.rotation_euler = (rnd0.uniform(1.0, 1.5), 0, rnd0.uniform(0, 6.28)); o.parent = bk
        o.hide_render = False; o.keyframe_insert("hide_render", frame=max(1, F(T_POUR0 + 0.6) - 1))   # they are what pours out: gone from it once poured
        o.hide_render = True; o.keyframe_insert("hide_render", frame=F(T_POUR0 + 0.6))
    B0 = Vector((0.31, -0.16, TOP + 0.005))          # on the table by his right hand
    def over(t): return pan_pt(1, t) + Vector((0.12, 0.06, 0.13))   # a little behind the pan: the beam stays clear in front
    SET_S = 1.4                                   # set down slowly: a quick one whipped his elbow over
    END = Vector((0.2, -0.47, TOP + 0.005))        # set down at the table's front edge, in clear view in front of the heap   # back where it came from: he held it there at the start, so his arm can reach it; set down at his side, clear of the heap so we see it land
    def bp(t):
        if t < T_LIFT: return B0
        if t < T_TIP1: return B0.lerp(over(t), ease((t - T_LIFT) / (T_TIP1 - T_LIFT)))
        if t < T_POUR1 + 0.25: return over(t)
        return over(T_POUR1 + 0.25).lerp(END, ease(min(1.0, (t - T_POUR1 - 0.25) / SET_S)))
    def brot(t):
        a = 0.0 if t < T_TIP1 - 0.35 else min(1.0, (t - T_TIP1 + 0.35) / 0.5) * 1.9
        if t > T_POUR1 + 0.25: a = 1.9 * (1 - ease(min(1.0, (t - T_POUR1 - 0.25) / (SET_S * 0.7))))
        return (0, -a, 0)
    follow(bk, bp, 0.0, DUR, rot_fn=brot)
    T_LET = T_POUR1 + 0.25 + SET_S + 0.2                        # the basket is down: he lets go
    reach(data, R, lambda t: bk.matrix_world @ Vector((0.0, 0.0, 0.085)) if (sc.frame_set(F(t)) or True) else None, 0.0, T_LET, lead=0.05, back=0.9, elbow_out=0.45)
    # the stream: flowers fall from the basket's mouth onto the right pan, heaping
    rnd = random.Random(3)
    N = 30; sched = [T_POUR0 + 0.1 + (T_POUR1 - T_POUR0 - 0.3) * (i / N) + rnd.uniform(-0.03, 0.03) for i in range(N)]
    fls = [SK.crocus(f"pour flower {i}", (0, 0, 0), seed=1000 + i, scale=0.55, own=False, mesh=bpy.data.meshes.get(f"crocus tmpl {i % 5}") or SK.crocus_mesh(f"crocus tmpl {i % 5}", seed=100 + i % 5)) for i in range(N)]
    PRW = PR_ * S
    def land(x, y, t):
        c = pan_pt(1, t); d = math.hypot(x - c.x, y - c.y)
        if d > PRW: return None
        return c.z + 0.008 + 0.07 * max(0.0, 1 - d / (PRW + 0.01)) * min(1.0, (t - T_POUR0) / (T_POUR1 - T_POUR0))
    props.pour(fls, NF, sched, lambda t: bk.matrix_world @ Vector((-0.09, 0.0, 0.06)) if (sc.frame_set(F(t)) or True) else None, land,
               kick_fn=lambda t: Vector((-0.12, 0.0, 0.0)), seed=5, lie=True)
    US = Vector((0.0, -1.2, 0.62))
    data.look_at(US, 0.0, max_yaw=20, blend=0.0)
    data.look_at(over(1.0), 0.5, max_yaw=35)
    data.look_at(BC + Vector((0, 0, 0.2)), T_POUR1 - 0.3, max_yaw=35)
    data.look_at(US, T_POUR1 + 0.6, max_yaw=20)
    data.idle(0.0, DUR)
    data.expression("determined", 0.3, T_POUR1)
    # "you're paying for all those hands": his free hand comes up open to us, palm out, and he grins
    T_HANDS = T_LET + 0.1
    up = lambda t: acts._shoulder(data, L) + Vector((-0.12, -0.1, 0.14))     # up beside his face, clear of the beam
    reach(data, L, up, T_HANDS, DUR, lead=0.45, back=None, elbow_out=0.5)
    data._k(f"hand.{L}", T_HANDS, rot=(-80, 0, 0)); data._k(f"hand.{L}", DUR, rot=(-80, 0, 0))
    data.expression("happy", T_POUR1 + 0.35, DUR, blend=0.45)
    data.alive(T_HANDS + 0.3, DUR, seed=5)
    data.blink(1.5)
    data.finish()
    soft_key("balance key", (-0.6, -1.0, 1.1), tuple(BC + Vector((0, 0, 0.2))), energy=24, size=32)
    soft_key("jar key", (-0.5, -0.7, 0.55), tuple(BC + Vector((-0.2, 0, 0.1))), energy=10, size=14)   # lights the jar's red
    C0, L0 = Vector((0.0, -1.3, 1.0)), Vector((0.0, -0.25, 0.6))    # close and above: his face clear over the balance and the heap
    C1, L1 = Vector((0.0, -1.22, 0.98)), Vector((0.0, -0.26, 0.59))   # pushes in as the beam comes level: the payoff gets its beat
    cam = K.camera(tuple(C0), tuple(L0), lens=31, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(max(0.0, t - T_POUR1 + 0.3) / (DUR - T_POUR1 + 0.3))), L0.lerp(L1, ease(max(0.0, t - T_POUR1 + 0.3) / (DUR - T_POUR1 + 0.3))), Vector((0.0, -0.25, 0.5))))
    return dict(**where, data=data, rest=1, grips=("pour basket", "jar"),
                conseq=[("the flowers pour onto the right pan", lambda: meshes(fls), T_POUR0 + 0.3, T_POUR1 + 0.3),
                        ("the beam levels: the tiny jar balances a heap of flowers", lambda: meshes([bal, jar]) + meshes(fls), T_POUR1, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
