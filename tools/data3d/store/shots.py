"""THE SELF-CHECKOUT SHORT, one SHOT PER BEAT (caaleb, 2026-11-11: "we need to do beats like with the 2D scenes ...
there needs to be an ultra wide shot so they can see what percentage of lines have been replaced"). Storyboard he OK'd:

  1 hook     "sold as the future... costing stores a fortune": close on a self-checkout that flashes red and spits
             money out of its slots, Data recoiling from it.
  2 beat 1   "9 out of 10 chains": ultra-wide down a row of TEN lanes; Data throws a big lever and 9 of the 10 flip,
             one after another, from cashier lanes to self-checkout. One staffed lane is left.
  3 beat 2   "half a million cashier jobs gone": cashiers in aprons file out through the staff door Data holds open,
             a wall calendar flipping through ten years beside it.
  4 beat 3   "stores lose more than twice as much": a cashier lane and a self-checkout side by side, a clear LOSSES jar
             in front of each; Data pours coins into both and the self-checkout jar fills to more than twice the height.
  5 closing  "the machine took the job and it's still losing the money": pull back from Data to the whole row, every
             lane a self-checkout, every lamp blinking red; he shrugs at the lens and waves.

    usage: SHOT=n python -I shots.py OUTDIR [SPP] [PCT]   env: NARR=narration.json | STILL=<local t> | STEP | FRAMES=a-b
Frames are written with GLOBAL numbers (the shot's start in the narration + local frame), so five shot folders merge
into one sequence. Prints 'FRAME n seconds'."""
import sys, os, math, json, time, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import bpy
from mathutils import Vector, Matrix
import scene_kit as K, acts, style, built
from acts import FPS, ease, ease_out, ease_in, ease_out_back, lerp

SHOT = int(os.environ.get("SHOT", "2"))
OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/tmp/shots"
SPP = int(sys.argv[2]) if len(sys.argv) > 2 else 24
PCT = int(sys.argv[3]) if len(sys.argv) > 3 else 60

# ---------------------------------------------------------------- timing from the voice
NARR = os.environ.get("NARR")
if NARR: W = json.load(open(NARR))["windows"]
else:    W = [[0, 4.2], [4.2, 9.2], [9.2, 14.7], [14.7, 19.7], [19.7, 25.2]]   # the 11-11 Charon read, near enough to stage
T0 = 0.0 if SHOT == 1 else W[SHOT - 1][0]
T1 = W[SHOT][0] if SHOT < 5 else W[4][1] + 0.6
G0 = int(round(T0 * FPS))                     # global frame offset: local frame f is written as G0 + f
NF = int(round(T1 * FPS)) - G0 + (1 if SHOT == 5 else 0)
DUR = NF / FPS
F = lambda t: int(round(t * FPS)) + 1
acts.F = F

sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)
sc.frame_start = 1; sc.frame_end = NF

ROW10 = [-2.79 + 0.62 * i for i in range(10)]


def key_loc(o, t, loc):
    o.location = loc; o.keyframe_insert("location", frame=F(t))


def key_rot(o, t, rot):
    o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=F(t))


def hide_from(root, t, show=False):
    for o in [root] + list(root.children_recursive):
        o.hide_render = show; o.keyframe_insert("hide_render", frame=max(1, F(t) - 1))
        o.hide_render = not show; o.keyframe_insert("hide_render", frame=F(t))


def person(name, loc, yaw=0.0):
    """the people of this world are MINIMAL (caaleb, 2026-11-11: "the less the better"): a faceless rounded figure, a
    head, a body in the staff blue, two legs. No face, hair, hands, badges. Every part is a DIRECT child of the root.
    Front is -Y; yaw turns it."""
    root = K.empty(name, loc); L = Vector(loc); s = 1.65 * K.U / 0.924
    body = K.mat("person body", "#2F6FA6", rough=0.6); head = K.mat("person head", "#E2D6CA", rough=0.55); leg = K.mat("person legs", "#33363C", rough=0.6)
    P = lambda ox, oy, oz: Vector((L.x + ox, L.y + oy, L.z + oz * s))
    for sg in (-1, 1):
        K.capsule("leg", P(sg * 0.055, 0, 0.44), P(sg * 0.055, 0, 0.05), 0.05, leg, parent=root)
    t = K.capsule("body", P(0, 0, 0.47), P(0, 0, 0.74), 0.15, body, parent=root, ra=0.13, rb=0.15); t.scale = (1.0, 0.72, 1.0)
    K.sph("head", P(0, 0, 0.9), 0.1, head, scale=(1.0, 1.0, 1.08), parent=root)
    root.rotation_euler = (0, 0, yaw)
    return root


def build_set(xs, kiosk_lanes, staffed=()):
    """the approved store (floor, walls, back shelf, aisles) with a lane at each x. kiosk_lanes: indices that get a
    kiosk (built below the floor; raise() brings it up). staffed: indices whose register gets a clerk."""
    K.floor(); K.walls(); K.gondola(x0=min(-3.5, xs[0] - 0.9), x1=max(4.8, xs[-1] + 1.2)); K.aisles()
    lanes = [K.checkout_lane(f"lane{i + 1}", x, number=i + 1, with_cashier=False) for i, x in enumerate(xs)]
    kiosks = {}
    for i in kiosk_lanes:
        kk = K.kiosk(f"kiosk{i + 1}", lanes[i]["kiosk_spot"], lanes[i]["h"]); kiosks[i] = kk
    clerks = {}
    for i in staffed:
        ln = lanes[i]; w = 0.52 * K.U
        clerks[i] = person(f"clerk {i + 1}", (ln["x"] - w * 0.78, 0.32 + 1.5 * K.U * 0.45, 0), yaw=math.radians(90))
    for ln in lanes:
        K.contact_shadow(ln["counter"].name + " shadow", (ln["x"], 0.32 + 1.5 * K.U / 2), rx=0.52 * K.U / 2 + 0.08, ry=1.5 * K.U / 2 + 0.08, parent=ln["counter"])
    for c in clerks.values(): K.contact_shadow(c.name + " shadow", c.location, rx=0.17, ry=0.12, parent=c)
    return lanes, kiosks, clerks


def kiosk_up(kk, ln):
    """the kiosk stands where the counter was, from frame 1"""
    kk["root"].location.z = 0.0
    ln["counter"].location.z = -3.0


def convert(ln, kk, t_go):
    """the counter lurches and plunges; the kiosk rises in its place, its screen lighting as it arrives"""
    counter = ln["counter"]; h = ln["h"]; cl = Vector(counter.location); kr = kk["root"]; kh = kk["h"]
    kr.location.z = -kh - 0.05; kr.keyframe_insert("location", frame=1)
    key_loc(counter, t_go, cl); key_rot(counter, t_go, (0, 0, 0))
    key_loc(counter, t_go + 0.18, cl + Vector((0, 0, -0.06))); key_rot(counter, t_go + 0.18, (0.06, 0, 0))
    key_loc(counter, t_go + 0.3, cl + Vector((0, 0, -0.04))); key_rot(counter, t_go + 0.3, (0.02, 0, 0))
    key_loc(counter, t_go + 0.55, cl + Vector((0, 0, -h - 0.35))); key_rot(counter, t_go + 0.55, (0, 0, 0))
    hide_from(counter, t_go + 0.57)
    t_up0, t_up1 = t_go + 0.5, t_go + 1.0
    for f in range(F(t_up0), F(t_up1) + 1):
        u = (f - F(t_up0)) / (F(t_up1) - F(t_up0)); kr.location.z = lerp(-kh - 0.05, 0.0, ease_out_back(u)); kr.keyframe_insert("location", frame=f)
    em = kk["screen_mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    em.default_value = 0.0; em.keyframe_insert("default_value", frame=1)
    for t, v in ((t_up0 + 0.3, 0.0), (t_up1, 0.9)): em.default_value = v; em.keyframe_insert("default_value", frame=F(t))


def screens_on(kiosks):
    for kk in kiosks.values():
        em = kk["screen_mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]; em.default_value = 0.9


def blink_red(kiosks, t_on, t_off, rate=2.5):
    """every self-checkout's lane lamp and terminal go red and blink; its main screen takes a red wash"""
    on = lambda t: t_on <= t < t_off
    ph = lambda t: int((t - t_on) * rate) % 2 == 0
    for name, red, dim in (("lane lamp", (1.0, 0.08, 0.05, 1.0), (0.25, 0.02, 0.01, 1.0)), ("terminal screen", (1.0, 0.25, 0.2, 1.0), (0.55, 0.12, 0.1, 1.0))):
        m = bpy.data.materials.get(name)
        if not (m and m.use_nodes): continue
        b = m.node_tree.nodes.get("Principled BSDF")
        cols = [i for i in (b.inputs.get("Base Color"), b.inputs.get("Emission Color")) if i is not None and not i.is_linked]
        rest = [tuple(i.default_value) for i in cols]
        for f in range(1, NF + 1):
            t = (f - 1) / FPS
            for i, r in zip(cols, rest): i.default_value = ((red if ph(t) else dim) if on(t) else r); i.keyframe_insert("default_value", frame=f)
    for sm in {id(k["screen_mat"]): k["screen_mat"] for k in kiosks.values()}.values():
        nt = sm.node_tree; b = nt.nodes.get("Principled BSDF")
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'; mix.inputs[7].default_value = (1.0, 0.1, 0.07, 1.0)
        n = 0
        for inp in (b.inputs.get("Emission Color"), b.inputs.get("Base Color")):
            if inp is None or not inp.is_linked: continue
            src = inp.links[0].from_socket
            if n == 0: nt.links.new(src, mix.inputs[6])
            nt.links.new(mix.outputs[2], inp); n += 1
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; mix.inputs[0].default_value = (0.85 if ph(t) else 0.55) if on(t) else 0.0; mix.inputs[0].keyframe_insert("default_value", frame=f)


def more_panels():
    """the lit ceiling runs the whole width of a ten-lane row"""
    for x in (-4.0, -2.8, 4.4):
        for y in (-0.9, 0.6):
            ld = bpy.data.lights.new(f"panel {x}_{y}", 'AREA'); ld.energy = 12; ld.color = (1.0, 0.97, 0.92); ld.shape = 'RECTANGLE'; ld.size = 1.1; ld.size_y = 0.3
            o = bpy.data.objects.new(f"panel {x}_{y}", ld); o.location = (x, y, 2.45); bpy.context.collection.objects.link(o)
            o.rotation_euler = Vector((0, 0, -1)).to_track_quat('-Z', 'Y').to_euler()


def camera_path(cam, fn, f0=1, f1=None):
    """fn(t) -> (loc, look, focus_point)"""
    for f in range(f0, (f1 or NF) + 1):
        t = (f - 1) / FPS; loc, look, foc = fn(t)
        loc = Vector(loc); look = Vector(look)
        cam.location = loc; cam.keyframe_insert("location", frame=f)
        cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.dof.focus_distance = (Vector(foc) - loc).length; cam.data.dof.keyframe_insert("focus_distance", frame=f)


def grip_follow(data, side, point_fn, t0, t1, elbow_out=0.5):
    """one hand ON a moving thing every frame (a lever handle, a sack's neck)"""
    for f in range(F(t0), F(t1) + 1):
        t = (f - 1) / FPS; sc.frame_set(f); data._arm_ik(side, Vector(point_fn(t)), t, elbow_out)


def near_hand(data, p):
    """the rig names its bones from the viewer's side: decide the hand by geometry"""
    sc.frame_set(1); bpy.context.view_layer.update()
    return min("LR", key=lambda s: (acts._shoulder(data, s) - Vector(p)).length)


def load_data():
    import character as CH
    return CH.load(sc)


# ================================================================ SHOT 1: the hook
def shot1():
    xs = K.LANE_X; lanes, kiosks, _ = build_set(xs, range(4))
    for i in range(4): kiosk_up(kiosks[i], lanes[i])
    screens_on(kiosks)
    kk = kiosks[1]; kx, ky = lanes[1]["kiosk_spot"].x, lanes[1]["kiosk_spot"].y
    data = load_data()
    data.place(kx - 0.36, ky - 0.42, 28)                 # beside the machine, his face to the lens from frame one (62 was a profile)
    data.expression("surprised", 0.0, DUR)
    sc.frame_set(1); p = data.pos()
    # recoiling, hands up by his face, then a step back as the money keeps coming
    fw = data.forward(); rt = Vector((math.cos(data.arm.rotation_euler.z), math.sin(data.arm.rotation_euler.z), 0))
    data.walk_to((p.x - 0.12, p.y - 0.14), 0.7, 1.4)
    for s_ in "LR":
        def up(t, s_=s_):
            sc.frame_set(F(t)); bpy.context.view_layer.update(); sh = acts._shoulder(data, s_); fw_ = data.forward()
            out = (sh - data.pos()); out.z = 0; out = out.normalized() if out.length > 1e-4 else Vector((0, 0, 0))
            wob = 0.015 * math.sin(t * 9 + (0 if s_ == "L" else 2))
            return sh + Vector((0, 0, 0.1 + wob)) + fw_ * 0.08 + out * 0.09
        grip_follow(data, s_, up, 0.0, DUR, elbow_out=1.2)
    money = (kx - 0.25, ky - 0.75, 0.7)                     # the cloud of bills between him and the lens: his face reads from frame one
    data.look_at(money, 0.0, max_yaw=60, blend=0.0)
    data.look_at(money, 1.3, max_yaw=60)
    data.look_at((-0.15, -1.6, 0.7), 1.8, max_yaw=55)       # to the lens: can you believe this
    data.look_at((-0.15, -1.6, 0.7), DUR, max_yaw=55)
    for tb in (1.5, 3.4): data.blink(tb)
    data.finish()
    blink_red({1: kk}, 0.0, DUR + 1, rate=3.0)
    # money: bills burst out of the cash and receipt slots, fly toward the lens and flutter down
    bill_m = K.mat("bill", "#5E8F5A", rough=0.6); band_m = K.mat("bill band", "#D9E6C8", rough=0.6)
    rnd = random.Random(11); sc.frame_set(1); bpy.context.view_layer.update()
    src = Vector((kx + 0.1, ky - 0.2, 0.47))
    for n in range(130):
        ts = rnd.uniform(-1.6, DUR - 0.3)
        v = Vector((rnd.uniform(-0.55, 0.25), rnd.uniform(-1.0, -0.45), rnd.uniform(0.9, 1.6)))
        spin = Vector((rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-6, 6)))
        b = K.box(f"bill {n}", tuple(src), (0.1, 0.045, 0.0012), bill_m, bev=0)
        K.box(f"bill band {n}", (src.x, src.y, src.z + 0.0007), (0.04, 0.047, 0.0004), band_m, bev=0, parent=b)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = t - ts
            if u < 0: loc = src - Vector((0, -0.05, 0.02)); sc_ = 0.0
            else:
                drag = 1 - math.exp(-2.2 * u)
                loc = src + Vector((v.x * drag / 2.2, v.y * drag / 2.2, v.z * drag / 2.2 - 0.35 * u * u))
                loc.x += 0.04 * math.sin(6 * u + n); loc.z = max(0.004, loc.z); sc_ = min(1.0, u / 0.06)
            b.location = loc; b.keyframe_insert("location", frame=f)
            b.scale = (sc_, sc_, sc_); b.keyframe_insert("scale", frame=f)
            r = spin * max(0.0, u) if loc.z > 0.005 else Vector((0, 0, spin.z * 0.1))
            b.rotation_euler = (r.x, r.y, r.z); b.keyframe_insert("rotation_euler", frame=f)
    cam = K.camera((kx - 0.95, -1.55, 0.62), (kx - 0.12, ky - 0.15, 0.55), lens=34, fstop=2.8)
    camera_path(cam, lambda t: ((kx - 0.95 + 0.06 * t, -1.55 + 0.1 * ease(t / DUR), 0.62), (kx - 0.12, ky - 0.15, 0.55), (kx - 0.3, ky - 0.4, 0.5)))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1)


# ================================================================ SHOT 2: 9 of 10, the ultra-wide
def shot2():
    lanes, kiosks, clerks = build_set(ROW10, range(1, 10), staffed=(0,))
    T_PULL0, T_PULL1 = 0.45, 0.95
    for k, i in enumerate(range(1, 10)): convert(lanes[i], kiosks[i], 1.05 + 0.27 * k)
    data = load_data()
    # the lever stands at the front of the row, Data beside it facing the lens
    lx, ly = ROW10[0] - 0.3, -0.42
    ped = K.mat("lever body", "#2E3136", rough=0.45); red = K.mat("lever knob", "#C6392B", rough=0.35)
    steel = K.mat("lever steel", "#B3B7BB", rough=0.3, metal=0.9); plate = K.mat("lever plate", "#C8643A", rough=0.5)
    K.box("lever base", (lx, ly, 0.03), (0.22, 0.18, 0.06), ped, bev=0.01)
    K.box("lever post", (lx, ly, 0.22), (0.12, 0.1, 0.36), ped, bev=0.012)
    K.box("lever plate", (lx, ly - 0.052, 0.3), (0.09, 0.004, 0.12), plate, bev=0.002)
    piv = Vector((lx, ly, 0.42)); arm = K.empty("lever pivot", tuple(piv))
    K.cyl("lever hub", tuple(piv), 0.035, 0.13, steel, rot=(0, math.radians(90), 0), v=24, parent=arm)
    LL = 0.24
    K.cyl("lever rod", (lx, ly, 0.42 + LL / 2), 0.014, LL, steel, v=16, parent=arm)
    K.sph("lever ball", (lx, ly, 0.42 + LL), 0.04, red, parent=arm)
    A0, A1 = math.radians(-35), math.radians(55)            # about x: up and back, thrown forward and down toward the lens
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = ease((t - T_PULL0) / (T_PULL1 - T_PULL0))
        arm.rotation_euler = (lerp(A0, A1, u), 0, 0); arm.keyframe_insert("rotation_euler", frame=f)
    knob = lambda t: (sc.frame_set(F(t)), bpy.context.view_layer.update(), arm.matrix_world @ Vector((0, 0, LL)))[2]
    data.place(lx - 0.02, ly - 0.24, -50)                 # to the lever's right (screen right), facing the lens
    data.expression("happy", 0.0, 1.0)
    side = near_hand(data, knob(0.0))
    grip_follow(data, side, knob, 0.0, T_PULL1 + 0.12, elbow_out=0.4)
    data.release(T_PULL1 + 0.15)
    data.look_at((-0.2, -2.6, 0.6), 0.0, max_yaw=40, blend=0.0)
    data.look_at((ROW10[5], 0.8, 0.5), 1.2, max_yaw=60)    # watching the row go
    data.look_at((ROW10[8], 0.8, 0.5), 3.0, max_yaw=60)
    data.expression("surprised", 1.4, 3.6)
    data.look_at((-1.0, -4.0, 1.3), 3.9, max_yaw=45)       # then to us
    data.expression("happy", 3.8, DUR)
    data.idle(T_PULL1 + 0.6, DUR)
    for tb in (0.3, 2.4, 4.3): data.blink(tb)
    data.finish()
    screens_on({})
    c = clerks[0]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; c.rotation_euler = (0, 0, math.radians(90 + 3 * math.sin(t * 2.6))); c.keyframe_insert("rotation_euler", frame=f)
    # the camera: high in the front-left corner, the row receding diagonally; a slow drift for life
    ex = ROW10[-1] + 1.15   # the store's end wall closes the far side of the shot
    br = built.brick_mat("end brick"); K.box("end wall", (ex + 0.1, 1.0, K.WALL_H / 2 + 0.3), (0.2, 9.0, K.WALL_H + 0.6), br, bev=0)
    K.box("end base", (ex - 0.01, 1.0, 0.05), (0.03, 9.0, 0.1), K.mat("base board"), bev=0.002)
    for y in (-1.6, 0.0, 1.6):
        ld = bpy.data.lights.new(f"end wash {y}", 'AREA'); ld.energy = 60; ld.size = 1.2; ld.color = (1.0, 0.95, 0.88)
        o = bpy.data.objects.new(f"end wash {y}", ld); o.location = (ex - 1.2, y, 2.2); bpy.context.collection.objects.link(o)
        o.rotation_euler = (Vector((ex, y, 0.9)) - o.location).to_track_quat('-Z', 'Y').to_euler()
    CA, LA = Vector((ROW10[0] - 1.25, -1.15, 1.45)), Vector((ROW10[6], 1.25, 0.15))
    cam = K.camera(tuple(CA), tuple(LA), lens=16, fstop=8.0)
    camera_path(cam, lambda t: (CA + Vector((0.1, 0.12, 0)) * (t / DUR), LA + Vector((0.08, 0, 0)) * (t / DUR), (ROW10[2], 0.6, 0.3)))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=NF)


# ================================================================ SHOT 3: the jobs walk out
def shot3():
    xs = K.LANE_X; lanes, kiosks, _ = build_set(xs, range(4))
    for i in range(4): kiosk_up(kiosks[i], lanes[i])
    screens_on(kiosks)
    # the staff-room wall: a partition at x = WX, its face toward -x, with a door opening at y in [DY0, DY1]
    WX, DY0, DY1, DH = 2.45, -0.62, -0.02, 1.25
    wall = K.mat("staff wall", "#D9D5CE", rough=0.75); frame = K.mat("door frame", "#3A3D42", rough=0.5); door_m = K.mat("staff door", "#5B6067", rough=0.45)
    K.box("staff wall front", (WX + 0.05, (-2.2 + DY0) / 2, 1.2), (0.1, DY0 + 2.2, 2.4), wall, bev=0.004)
    K.box("staff wall back", (WX + 0.05, (DY1 + 1.25) / 2, 1.2), (0.1, 1.25 - DY1, 2.4), wall, bev=0.004)
    K.box("staff wall top", (WX + 0.05, (DY0 + DY1) / 2, (DH + 2.4) / 2), (0.1, DY1 - DY0, 2.4 - DH), wall, bev=0.004)
    for y in (DY0, DY1): K.box("door jamb", (WX - 0.005, y, DH / 2), (0.12, 0.04, DH), frame, bev=0.004)
    K.box("door head", (WX - 0.005, (DY0 + DY1) / 2, DH), (0.12, DY1 - DY0 + 0.04, 0.05), frame, bev=0.004)
    K.box("staff only plate", (WX - 0.006, (DY0 + DY1) / 2, DH + 0.12), (0.004, 0.32, 0.09), K.mat("sign ivory"), bev=0.002)
    K.text("staff only", "STAFF ONLY", (WX - 0.01, (DY0 + DY1) / 2, DH + 0.12), 0.045, (math.radians(90), 0, math.radians(-90)), K.mat("sign navy"), extrude=0.001)
    # the backroom glows: a light beyond the door
    ld = bpy.data.lights.new("backroom", 'AREA'); ld.energy = 25; ld.size = 0.8; ld.color = (1.0, 0.9, 0.75)
    bo = bpy.data.objects.new("backroom", ld); bo.location = (WX + 0.8, (DY0 + DY1) / 2, 1.0); bpy.context.collection.objects.link(bo)
    bo.rotation_euler = Vector((-1, 0, -0.3)).to_track_quat('-Z', 'Y').to_euler()
    K.box("backroom floor", (WX + 1.5, 0, -0.005), (3, 4, 0.01), K.mat("backroom floor", "#6A6660", rough=0.8), bev=0)
    # the calendar on the wall beside the door, at Data's height: he tears off a year as each one walks out
    cy = DY0 - 0.78; cz = 0.66
    K.box("calendar back", (WX - 0.008, cy, cz), (0.012, 0.3, 0.36), K.mat("calendar paper", "#F4F1EA", rough=0.8), bev=0.003)
    K.box("calendar band", (WX - 0.016, cy, cz + 0.15), (0.004, 0.3, 0.07), K.mat("sale red", "#C6392B", rough=0.5), bev=0.001)
    years = list(range(2014, 2025)); tY0, tY1 = 0.5, DUR - 0.9
    flips = []
    for k, yr in enumerate(years):
        o = K.text(f"year {yr}", str(yr), (WX - 0.017, cy, cz - 0.03), 0.1, (math.radians(90), 0, math.radians(-90)), K.mat("sign navy"), extrude=0.002)
        ta = tY0 + (tY1 - tY0) * k / (len(years) - 1); tb = tY0 + (tY1 - tY0) * (k + 1) / (len(years) - 1) if k < len(years) - 1 else DUR + 1
        o.hide_render = k > 0; o.keyframe_insert("hide_render", frame=1)
        if k > 0: o.hide_render = False; o.keyframe_insert("hide_render", frame=F(ta)); flips.append(ta)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=F(tb))
    # the cashiers: a line of them in aprons walk from the lanes, along the front, and out through the door
    yl = (DY0 + DY1) / 2; n = 7; speed = 0.62; gap = 0.42
    for k in range(n):
        c = person(f"staff {k}", (0, 0, 0), yaw=0)
        x_start = WX - 0.4 - 0.9 - k * gap - 0.2
        t_go = 0.0; x_end = WX + 0.9
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; x = x_start + speed * max(0.0, t - t_go)
            if x < WX - 0.55:   # walking along +x, face +x
                loc = Vector((x, yl, 0)); yaw = math.radians(90)
            else:
                loc = Vector((x, yl, 0)); yaw = math.radians(90)
            loc.z = 0.012 * abs(math.sin((t - t_go) * 9.0 + k))
            c.location = loc; c.keyframe_insert("location", frame=f); c.rotation_euler = (0, 0, yaw + math.radians(4 * math.sin(t * 9.0 + k))); c.keyframe_insert("rotation_euler", frame=f)
            hidden = x > WX + 0.7
            c.hide_render = hidden; c.keyframe_insert("hide_render", frame=f)
            for ch in c.children_recursive: ch.hide_render = hidden; ch.keyframe_insert("hide_render", frame=f)
        K.contact_shadow(c.name + " shadow", (0, 0), rx=0.17, ry=0.12, parent=c)
    # Data stands at the calendar and tears a year off as each one goes
    data = load_data()
    data.place(WX - 0.3, cy + 0.26, 105)
    page = Vector((WX - 0.03, cy, cz + 0.02))
    side = near_hand(data, page)
    rest = lambda t: (sc.frame_set(F(t)), acts._shoulder(data, side) + Vector((0, 0, -0.2)) - data.forward() * 0.02)[1]
    data._arm_ik(side, rest(0.0), 0.0, 0.3)
    for ta in flips:
        data._arm_ik(side, page + Vector((0, 0, 0.08)), ta - 0.12, 0.5)
        data._arm_ik(side, page + Vector((-0.02, -0.03, -0.1)), ta + 0.08, 0.5)
        data._arm_ik(side, page + Vector((-0.06, -0.02, -0.04)), ta + 0.2, 0.5)
    data._arm_ik(side, rest(DUR), DUR, 0.3)
    data.look_at((WX - 0.8, yl, 0.75), 0.0, max_yaw=70, blend=0.0)
    data.look_at((WX - 0.8, yl, 0.75), 1.5, max_yaw=70)
    data.expression("worried", 0.8, DUR)
    data.look_at((0.6, -2.4, 0.8), 2.4, max_yaw=70)     # a look to us: they're all going
    data.look_at((0.6, -2.4, 0.8), 3.5, max_yaw=70)
    data.look_at((WX - 0.5, yl, 0.75), 4.2, max_yaw=70)
    data.look_at((WX - 0.5, yl, 0.75), DUR, max_yaw=70)
    for tb in (1.0, 3.0, 4.6): data.blink(tb)
    data.finish()
    cam = K.camera((0.65, -2.75, 0.8), (1.9, -0.8, 0.55), lens=24, fstop=4.0)
    camera_path(cam, lambda t: ((0.65 + 0.08 * t / DUR, -2.75, 0.8), (1.9, -0.8, 0.55), (WX - 0.3, cy, 0.6)))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1)


# ================================================================ SHOT 4: twice the losses
def shot4():
    xs = [-0.5, 0.5]
    lanes, kiosks, clerks = build_set(xs, (1,), staffed=(0,))
    kiosk_up(kiosks[1], lanes[1]); screens_on(kiosks)
    glass = K.mat("jar glass", "#E8F0F4", rough=0.03)
    try:
        b = glass.node_tree.nodes["Principled BSDF"]; b.inputs["Transmission Weight"].default_value = 1.0; b.inputs["IOR"].default_value = 1.45
    except KeyError: pass
    gold = K.mat("coins", "#E9BE45", rough=0.22, metal=1.0)
    nt = gold.node_tree; gb = nt.nodes["Principled BSDF"]
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'; wv.inputs["Scale"].default_value = 60; wv.inputs["Distortion"].default_value = 3
    geo = nt.nodes.new("ShaderNodeNewGeometry"); nt.links.new(geo.outputs["Position"], wv.inputs["Vector"])   # world space: the bands keep their size as the fill grows
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; nt.links.new(wv.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], gb.inputs["Normal"])
    lid = K.mat("jar lid", "#2E3136", rough=0.5)
    JY = -0.34; JR = 0.1; JH = 0.48
    jars = {}
    for i, x in enumerate(xs):
        jx = -0.3 if i == 0 else 0.3          # in front of its own lane, close enough either side of Data to pour into
        K.cyl(f"jar {i}", (jx, JY, JH / 2 + 0.01), JR, JH, glass, v=48, bev=0.01)
        K.cyl(f"jar base {i}", (jx, JY, 0.006), JR + 0.01, 0.012, lid, v=48, bev=0.003)
        K.box(f"jar label {i}", (jx, JY - JR - 0.002, JH - 0.05), (0.17, 0.003, 0.06), K.mat("sign ivory"), bev=0.001)
        K.text(f"jar text {i}", "LOSSES", (jx, JY - JR - 0.005, JH - 0.05), 0.04, (math.radians(90), 0, 0), K.mat("sign navy"), extrude=0.001)
        fill = K.cyl(f"coin fill {i}", (jx, JY, 0.0), JR - 0.006, 1.0, gold, v=48, bev=0.0)
        for v in fill.data.vertices: v.co.z += 0.5            # origin at the bottom: scale z = height
        fill.location.z = 0.013
        jars[i] = (Vector((jx, JY, 0)), fill)
    K.contact_shadow("jar shadows", ((xs[0] + xs[1]) / 2, JY), rx=0.6, ry=0.12)
    # fills: the cashier jar to H_LO, the self-checkout jar to more than twice that
    H_LO, H_HI = 0.13, 0.33
    P0a, P0b = 0.5, 1.7            # pour into the cashier jar
    WALK0, WALK1 = 1.9, 2.4           # (no walk: he turns the sack from one jar to the other)
    P1a, P1b = 2.4, DUR - 1.2      # pour into the self-checkout jar
    for i, (h, a, b_) in enumerate(((H_LO, P0a + 0.15, P0b), (H_HI, P1a + 0.15, P1b))):
        fill = jars[i][1]
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = ease((t - a) / (b_ - a)); fill.scale = (1, 1, max(0.0005, h * u)); fill.keyframe_insert("scale", frame=f)
    # the sack: Data carries it in both hands and tips it over each jar
    sack_m = K.mat("sack", "#B08A58", rough=0.85); tie = K.mat("sack tie", "#5B4630", rough=0.8)
    sack = K.empty("sack", (0, 0, 0))
    K.sph("sack body", (0, 0, 0), 0.085, sack_m, scale=(1.0, 0.9, 1.05), parent=sack)
    K.cyl("sack neck", (0, 0, 0.1), 0.035, 0.05, sack_m, v=20, parent=sack)
    K.cyl("sack tie", (0, 0, 0.085), 0.039, 0.014, tie, v=20, parent=sack)
    K.text("sack sign", "$", (0, -0.078, 0.0), 0.08, (math.radians(90), 0, 0), K.mat("sack ink", "#3A2A1A", rough=0.8), extrude=0.003, parent=sack)
    data = load_data()
    ya = jars[0][0]; yb = jars[1][0]
    data.place(0.0, JY + 0.2, 0)                         # between the jars, facing the lens
    sc.frame_set(1); bpy.context.view_layer.update()
    def sack_at(t):
        hold = Vector((0.0, JY + 0.02, 0.5))
        if t < WALK0: j, pa, pb, sg = ya, P0a, P0b, -1
        else: j, pa, pb, sg = yb, P1a, P1b, 1
        u = ease((t - (pa - 0.35)) / 0.35) * (1 - ease((t - pb) / 0.35))
        over = Vector((j.x - sg * 0.07, JY + 0.0, JH + 0.14))
        return hold.lerp(over, u), sg * math.radians(110) * u
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; loc, tip = sack_at(t)
        sack.location = loc; sack.keyframe_insert("location", frame=f); sack.rotation_euler = (0, tip, 0); sack.keyframe_insert("rotation_euler", frame=f)
    def hands(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); M = sack.matrix_world
        return M @ Vector((-0.07, 0.0, 0.05)), M @ Vector((0.07, 0.0, 0.05))
    sc.frame_set(1); bpy.context.view_layer.update()
    sL = near_hand(data, hands(0)[0]); sR = "R" if sL == "L" else "L"
    grip_follow(data, sL, lambda t: hands(t)[0], 0.0, DUR, elbow_out=0.6)
    grip_follow(data, sR, lambda t: hands(t)[1], 0.0, DUR, elbow_out=0.6)
    data.look_at((ya.x, JY, 0.4), 0.0, max_yaw=55, blend=0.0)
    data.look_at((ya.x, JY, 0.4), P0b, max_yaw=55)
    data.look_at((yb.x, JY, 0.4), P1a, max_yaw=55)
    data.look_at((yb.x, JY, 0.4), P1b - 0.6, max_yaw=55)
    data.look_at((0.0, -2.2, 0.6), P1b, max_yaw=55)
    data.idle(0.0, DUR)        # to us, as the second jar tops out
    data.expression("surprised", P1b - 0.3, DUR)
    for tb in (1.2, 2.9, DUR - 0.5): data.blink(tb)
    data.finish()
    # the coin stream from the sack mouth into the jar while pouring
    coin_m = gold; rnd = random.Random(4)
    for k in range(46):
        pa, pb, j = (P0a, P0b, ya) if k < 16 else (P1a, P1b, yb)
        ts = rnd.uniform(pa, pb - 0.2); c = K.cyl(f"coin {k}", (0, 0, 0), 0.016, 0.004, coin_m, v=20, bev=0.001)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = t - ts
            if u < 0 or u > 0.5: c.scale = (0, 0, 0); c.keyframe_insert("scale", frame=f); continue
            top = JY  # unused
            z0 = JH + 0.12; z = z0 - 4.9 * u * u
            c.location = (j.x + rnd.uniform(-0.01, 0.01) * 0 + 0.01 * math.sin(k), JY + 0.01 * math.cos(k), z); c.keyframe_insert("location", frame=f)
            c.rotation_euler = (u * 12 + k, u * 7, 0); c.keyframe_insert("rotation_euler", frame=f)
            c.scale = (1, 1, 1) if z > 0.05 else (0, 0, 0); c.keyframe_insert("scale", frame=f)
    c0 = clerks[0]
    for f in range(1, NF + 1, 2):
        t = (f - 1) / FPS; c0.rotation_euler = (0, 0, math.radians(90 + 4 * math.sin(t * 2.3))); c0.keyframe_insert("rotation_euler", frame=f)
    cam = K.camera((0.0, -2.0, 0.66), (0.0, 0.0, 0.48), lens=24, fstop=4.0)
    camera_path(cam, lambda t: ((-0.06 + 0.12 * t / DUR, -2.0 + 0.12 * ease(t / DUR), 0.66), (0.0, 0.0, 0.48), (0.0, JY, 0.35)))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1)


# ================================================================ SHOT 5: the closing, the whole row
def shot5():
    lanes, kiosks, _ = build_set(ROW10, range(10))
    for i in range(10): kiosk_up(kiosks[i], lanes[i])
    screens_on(kiosks); blink_red(kiosks, 0.3, DUR + 1)
    data = load_data()
    data.place(0.0, -0.55, 0)
    data.expression("worried", 0.0, 1.8)
    data.look_at((0, -3, 0.75), 0.0, max_yaw=40, blend=0.0)
    data.act("shrug", 0.5, dur=0.28, hold=0.6)
    data.expression("happy", 2.0, DUR)
    if DUR > 4.0: data.act("wave", 2.4, dur=0.3, hold=1.2)    # while he is still big in frame; the pull-back then reveals the row
    data.idle(0.0, DUR)
    for tb in (1.9, DUR - 2.9): data.blink(tb)
    data.finish()
    cam = K.camera((0, -1.7, 0.62), (0, 0, 0.55), lens=26, fstop=4.0)
    def path(t):
        u = ease((t - 0.3) / (DUR - 0.8))
        loc = Vector((0, -1.7, 0.62)).lerp(Vector((0, -4.7, 1.25)), u)
        look = Vector((0, 0, 0.55)).lerp(Vector((0, 0.6, 0.62)), u)
        cam.data.lens = lerp(26, 17, u); cam.data.keyframe_insert("lens", frame=F(t))
        return loc, look, (0, -0.55, 0.5)
    camera_path(cam, path)
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1)


S = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}[SHOT]()
data = S["data"]; sc.frame_start = 1; sc.frame_end = NF
store = {"lanes": S["lanes"], "extra": [], "kiosks": S["kiosks"]}
built.apply(sc, store, S["rest"])
style.restyle()
key = style.lights(sc); more_panels()
built.relight(); built.feet_shadow(data)
if S.get("open_roof"):   # the camera is up in the roof: take the deck, joists, ducts and pendants out of its way
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type == 'MESH':
            zmin = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
            if zmin > 2.15: o.hide_render = True
style.follow_key(key, data, 1, NF)
style.render_settings(sc, SPP, PCT)
if os.environ.get("TEMPORAL_SAFE", "1") == "1":
    cy = sc.cycles; cy.adaptive_threshold = 0.01; cy.denoising_prefilter = 'ACCURATE'

os.makedirs(OUT, exist_ok=True)
if os.environ.get("DIAG"): exec(open(os.environ["DIAG"]).read()); sys.exit(0)
still = os.environ.get("STILL"); step = int(os.environ.get("STEP", "1")); fr = os.environ.get("FRAMES")
if still is not None: frames = [min(NF, F(float(still)))]
elif fr: a, b = fr.split("-"); frames = [f for f in range(int(a), int(b) + 1, step) if 1 <= f <= NF]
else: frames = list(range(1, NF + 1, step))
print(f"SHOT {SHOT} T0={T0:.2f} T1={T1:.2f} NF={NF} G0={G0}")
for f in frames:
    path = os.path.join(OUT, f"f{G0 + f:04d}.png")
    if os.path.exists(path): continue
    t0 = time.time(); sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print(f"FRAME {G0 + f} {time.time() - t0:.1f}", flush=True)
