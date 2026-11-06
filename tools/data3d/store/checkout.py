"""THE SHOT (10 s, 1080x1920, 24 fps): Data pushes a cart left to right past four checkout lanes, side-on, camera
leading him. As the cart's nose comes within TRIG_AHEAD of a lane its cashier walks off UPSTAGE, the counter sinks
with a lurch and a self-checkout kiosk rises in its place. Two far lanes stay staffed. At the end he lets go, turns
back, takes it in, then turns to camera with a shrug and a smile while the camera pushes in.
    usage: python -I checkout.py OUTDIR [SPP] [PCT]      env: STILL=<t> | STEP=10 | FRAMES=a-b
Skips frames whose file exists; prints 'FRAME n seconds'."""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
from mathutils import Vector
import scene_kit as K, acts, style
from acts import F, FPS, ease, ease_out, ease_in, ease_out_back, lerp

OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/tmp/checkout"
SPP = int(sys.argv[2]) if len(sys.argv) > 2 else 24
PCT = int(sys.argv[3]) if len(sys.argv) > 3 else 60

T_PUSH0, T_PUSH1, T_END = 0.5, 6.6, 10.0
X0, X1 = -0.72, 2.3
TRIG_AHEAD = 0.9
CAM_BASE = Vector((-0.55, -2.6, 0.72)); CAM_LOOK = Vector((0.45, 0.35, 0.42)); LOOK_AHEAD = 0.25; PUSH_IN = 1.5
BACK_Y = K.BACK_Y - 0.1

sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)
sc.frame_start = 1; sc.frame_end = F(T_END)

store = K.build_store()
cart = store["cart"]

# ---------------------------------------------------------------- Data
try:
    import character as CH; data = CH.load(sc); WHO = "character.py"
except Exception as e:  # noqa
    print("character.py not usable (%s); using stand-in" % e); import standin as CH; data = CH.load(sc); WHO = "standin"
data.place(X0, 0.0, 90)          # facing +x

# ---------------------------------------------------------------- the push, straight arm every frame
f0, f1 = acts.push(data, cart, (X1, 0.0), T_PUSH0, T_PUSH1)
# before the push: standing with hands on the bar
for f in range(1, f0):
    sc.frame_set(f)
cart_start = Vector(cart["root"].location)

# ---------------------------------------------------------------- lanes convert as the nose arrives
def cart_nose_x(t):
    sc.frame_set(F(t)); return acts.world(cart["nose"]).x

def lane_trigger(i):
    return T_PUSH0 + (K.LANE_X[i] - TRIG_AHEAD - X0) / (X1 - X0) * (T_PUSH1 - T_PUSH0)

def key_loc(o, t, loc, interp='BEZIER'):
    o.location = loc; o.keyframe_insert("location", frame=F(t))

def key_rot(o, t, rot):
    o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=F(t))

def hide_from(root, t):
    for o in [root] + list(root.children_recursive):
        o.hide_render = False; o.keyframe_insert("hide_render", frame=F(t) - 1)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=F(t))

def cashier_idle(root, t0, t1, yaw0, amp=2.0, period=2.3):
    for f in range(F(t0), F(t1) + 1):
        t = (f - 1) / FPS
        root.rotation_euler = (0, 0, yaw0 + math.radians(amp * math.sin(2 * math.pi * t / period)))
        root.keyframe_insert("rotation_euler", frame=f)

def cashier_watch(root, t0, t1, yaw0):
    """turn toward Data when he is within 1.3 m, from the idle"""
    for f in range(F(t0), F(t1) + 1):
        sc.frame_set(f); p = Vector(data.arm.location); c = Vector(root.location); d = p - c
        if d.length < 1.3:
            yaw = math.atan2(d.x, -d.y); cur = root.rotation_euler.z
            k = 0.35
            root.rotation_euler = (0, 0, cur + (yaw - cur) * k); root.keyframe_insert("rotation_euler", frame=f)

for i, ln in enumerate(store["lanes"]):
    t_go = lane_trigger(i)
    cash = ln["cashier"]; counter = ln["counter"]; kk = store["kiosks"][i]; h = ln["h"]
    yaw0 = cash.rotation_euler.z
    cashier_idle(cash, 0.0, t_go, yaw0)
    cashier_watch(cash, max(0, t_go - 1.2), t_go, yaw0)
    # walk off UPSTAGE: up the aisle then along the back wall to the left, never across his path
    c0 = Vector(cash.location)
    t1 = t_go + 0.25; t2 = t1 + (BACK_Y - c0.y) / 0.9; t3 = t2 + 1.8
    key_loc(cash, t1, c0); key_rot(cash, t1, (0, 0, math.radians(0)))   # face +y (upstage) : rest faces -Y so yaw=pi
    key_rot(cash, t1 + 0.15, (0, 0, math.pi))
    key_loc(cash, t2, Vector((c0.x, BACK_Y, 0))); key_rot(cash, t2, (0, 0, math.pi))
    key_rot(cash, t2 + 0.2, (0, 0, math.radians(90)))
    key_loc(cash, t3, Vector((c0.x - 1.8 * 1.0, BACK_Y, 0))); key_rot(cash, t3, (0, 0, math.radians(90)))
    # bob while walking
    for f in range(F(t1), F(t3) + 1):
        sc.frame_set(f); l = Vector(cash.location); l.z = 0.012 * abs(math.sin((f - F(t1)) * 0.55)); cash.location = l; cash.keyframe_insert("location", frame=f)
    hide_from(cash, t3 + 0.05)
    # counter: a lurch, then down through the floor; kiosk rises in its place
    ts = t_go + 0.7; cl = Vector(counter.location)
    key_loc(counter, ts, cl); key_rot(counter, ts, (0, 0, 0))
    key_loc(counter, ts + 0.18, cl + Vector((0, 0, -0.06))); key_rot(counter, ts + 0.18, (0.06, 0, 0))
    key_loc(counter, ts + 0.3, cl + Vector((0, 0, -0.04))); key_rot(counter, ts + 0.3, (0.02, 0, 0))
    key_loc(counter, ts + 1.1, cl + Vector((0, 0, -h - 0.35))); key_rot(counter, ts + 1.1, (0.0, 0, 0))
    hide_from(counter, ts + 1.15)
    kr = kk["root"]; kh = kk["h"]
    for f in range(F(ts + 0.9), F(ts + 1.9) + 1):
        u = (f - F(ts + 0.9)) / (F(ts + 1.9) - F(ts + 0.9)); z = lerp(-kh - 0.05, 0.0, ease_out_back(u))
        kr.location = (kr.location.x, kr.location.y, z); kr.keyframe_insert("location", frame=f)

for ln in store["extra"]:
    cashier_idle(ln["cashier"], 0.0, T_END, ln["cashier"].rotation_euler.z, amp=2.5, period=2.9)

# ---------------------------------------------------------------- the ending: let go, turn back, take it in, turn to camera, shrug
T_REL = T_PUSH1 + 0.1
data.release(T_REL)
for f in range(F(T_REL), F(T_END) + 1):     # cart rolls on a touch then stops
    sc.frame_set(F(T_PUSH1))
cart_end = Vector(cart["root"].location); cart_rot = cart["root"].rotation_euler.z
for t, dx in ((T_PUSH1, 0.0), (T_PUSH1 + 0.9, 0.22)):
    cart["root"].location = cart_end + Vector((dx, 0, 0)); cart["root"].keyframe_insert("location", frame=F(t))
data.turn_to(-90, T_REL + 0.2, T_REL + 0.9)          # face -x: back along the lanes
data.look_at((0.9, 0.6, 0.6), T_REL + 0.9)
data.expression("surprised", T_REL + 0.8, T_REL + 2.2)
data.look_at((-0.2, 0.6, 0.6), T_REL + 1.6)
data.turn_to(180, T_REL + 1.7, T_REL + 2.2)          # face -y: camera
data.look_at((CAM_BASE.x + 1.0, CAM_BASE.y + 1.2, 0.8), T_REL + 2.2)
data.act("shrug", T_REL + 2.3, dur=0.3, hold=0.45)   # ends inside the 10 s
data.expression("happy", T_REL + 2.3, T_END)
data.finish()

# ---------------------------------------------------------------- camera: leads him, pushes in at the turn
cam = K.camera(CAM_BASE, CAM_LOOK, lens=30, fstop=8)
for f in range(1, F(T_END) + 1):
    sc.frame_set(f); t = (f - 1) / FPS
    px = Vector(data.arm.location).x
    u_in = ease((t - (T_REL + 1.6)) / 1.2)
    loc = Vector((CAM_BASE.x + (px - X0) + LOOK_AHEAD * min(1, max(0, (t - T_PUSH0) / 0.6)) * (1 - u_in), CAM_BASE.y, CAM_BASE.z))
    look = Vector((px + LOOK_AHEAD, CAM_LOOK.y, CAM_LOOK.z))
    if u_in > 0:
        tgt = Vector((px, 0.0, 0.66)); look = look.lerp(tgt, u_in)
        loc = loc + (tgt - loc).normalized() * PUSH_IN * u_in
    cam.location = loc; cam.keyframe_insert("location", frame=f)
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.dof.focus_distance = (Vector((px, 0, 0.5)) - loc).length; cam.data.dof.keyframe_insert("focus_distance", frame=f)

# ---------------------------------------------------------------- look
style.restyle()
key = style.lights(sc)
style.follow_key(key, data, 1, F(T_END))
style.render_settings(sc, SPP, PCT)

# ---------------------------------------------------------------- measure
side = acts.near_side(data, cam) if True else "L"
mx, mean = acts.arm_bend(data, f0, f1, side)
mxo, meano = acts.arm_bend(data, f0, f1, "R" if side == "L" else "L")
sc.frame_set(F(3.0)); d_on = acts.hand_on_bar(data, cart, side)
print(f"DATA={WHO} near_side={side} arm_bend near max={mx:.2f} mean={mean:.2f} | far max={mxo:.2f} mean={meano:.2f} | hand->bar@3s={d_on*1000:.1f}mm")
for i in range(4): print(f"lane{i+1} trigger t={lane_trigger(i):.2f}s")

# ---------------------------------------------------------------- render
os.makedirs(OUT, exist_ok=True)
if os.environ.get("DIAG"): exec(open(os.environ["DIAG"]).read()); sys.exit(0)
still = os.environ.get("STILL"); step = int(os.environ.get("STEP", "1")); fr = os.environ.get("FRAMES")
if still is not None: frames = [F(float(still))]
elif fr: a, b = fr.split("-"); frames = list(range(int(a), int(b) + 1, step))
else: frames = list(range(1, F(T_END) + 1, step))
for f in frames:
    path = os.path.join(OUT, f"f{f:04d}.png")
    if os.path.exists(path): continue
    t0 = time.time(); sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t0:.1f}", flush=True)
