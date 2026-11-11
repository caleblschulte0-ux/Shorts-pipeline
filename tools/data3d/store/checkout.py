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
import scene_kit as K, acts
if K.DS: import style_DS as style   # LOOK=DS: the design-studio preset (set dressing switched in scene_kit)
else: import style
from acts import F, FPS, ease, ease_out, ease_in, ease_out_back, lerp

OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/tmp/checkout"
SPP = int(sys.argv[2]) if len(sys.argv) > 2 else 24
PCT = int(sys.argv[3]) if len(sys.argv) > 3 else 60

T_PUSH0, T_PUSH1, T_END = 0.5, 6.6, 10.0
T_CLOSE = None           # when he turns to the lens; default T_REL + 1.7 (the 10 s cut)
NARR = os.environ.get("NARR")   # narration.json from data3d_narrate.yml: the shot is timed to the voice
if NARR:
    import json as _j
    _w = _j.load(open(NARR))["windows"]          # [hook, beat 1, beat 2, beat 3, closing]
    T_PUSH0 = 0.3; T_PUSH1 = _w[3][0] - 0.1      # he pushes through the hook and the first two beats
    T_CLOSE = _w[4][0] - 0.25                    # turns to the lens as the closing line starts
    T_END = _w[4][1] + 0.6
X0, X1 = -0.72, 2.3
TRIG_AHEAD = 0.9         # the lane converts in the camera's LEAD space, right of the cart, not behind Data
CAM_BASE = Vector((-0.55, -2.67, 0.6)); CAM_LOOK = Vector((0.45, 0.35, 0.8)); LOOK_AHEAD = 0.25; PUSH_IN = 1.05; LENS = 40; FSTOP = 2.8   # tilted up: feet near 85% of the frame, the ceiling in shot
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
data.expression("neutral", 0.0)  # pin the resting face from frame 1: without a key the mouth cavity held an OPEN scale and read as a dark blob in profile

# ---------------------------------------------------------------- the push, straight arm every frame
f0, f1 = acts.push(data, cart, (X1, 0.0), T_PUSH0, T_PUSH1)
# a three-quarter face for the lens while he pushes: dead side-on, the camera saw the back of a ball with one eye-white
# dome and a floating brow; turned 30 degrees it reads as his face (eye, smile, nose) - pose for the one camera
sc.frame_set(F(T_PUSH0)); _p = data.pos()
data.look_at((_p.x + 0.55, _p.y - 1.0, 0.66), 0.0, max_yaw=52, blend=0.0)   # from the FIRST frame: the opening must not be the back of a ball
data.look_at((_p.x + 0.55, _p.y - 1.0, 0.66), T_PUSH0, max_yaw=52)   # a real three-quarter face for the lens: dead side-on his head is a featureless ball with the glasses edge-on
sc.frame_set(F(T_PUSH1)); _p = data.pos()
data.look_at((_p.x + 0.55, _p.y - 1.0, 0.66), T_PUSH1, max_yaw=52)   # HOLD the three-quarter face the whole push: with one key the head drifted back to profile toward the ending's look
data.gaze(T_PUSH0, 9, 0)   # +dx is his right: toward the lens
for tb in (1.6, 4.3, 6.0): data.blink(tb)
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
    ts = t_go + 0.5; cl = Vector(counter.location)
    key_loc(counter, ts, cl); key_rot(counter, ts, (0, 0, 0))
    key_loc(counter, ts + 0.18, cl + Vector((0, 0, -0.06))); key_rot(counter, ts + 0.18, (0.06, 0, 0))
    key_loc(counter, ts + 0.3, cl + Vector((0, 0, -0.04))); key_rot(counter, ts + 0.3, (0.02, 0, 0))
    key_loc(counter, ts + 0.55, cl + Vector((0, 0, -h - 0.35))); key_rot(counter, ts + 0.55, (0.0, 0, 0))   # the drop is a six-frame PLUNGE: a register corner poking through the floor reads as a stub, not a sink
    hide_from(counter, ts + 0.57)
    kr = kk["root"]; kh = kk["h"]; t_up0, t_up1 = ts + 0.5, ts + 1.0
    for f in range(F(t_up0), F(t_up1) + 1):
        u = (f - F(t_up0)) / (F(t_up1) - F(t_up0)); z = lerp(-kh - 0.05, 0.0, ease_out_back(u))
        kr.location = (kr.location.x, kr.location.y, z); kr.keyframe_insert("location", frame=f)
    # the screen lights up as it arrives
    em = kk["screen_mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for t, v in ((t_up0 + 0.3, 0.0), (t_up1, 0.9)):   # lights as it rises, blue
        em.default_value = v; em.keyframe_insert("default_value", frame=F(t))

for ln in store["extra"]:
    cashier_idle(ln["cashier"], 0.0, T_END, ln["cashier"].rotation_euler.z, amp=2.5, period=2.9)

# ---------------------------------------------------------------- the ending: let go, turn back, take it in, turn to camera, shrug
T_REL = T_PUSH1 + 0.1
if T_CLOSE is None: T_CLOSE = T_REL + 1.7
data.release(T_REL)
data.idle(T_REL + 0.45, T_END)
data.blink(T_REL + 1.65); data.blink(T_END - 0.6)
for _tb in range(int(T_REL + 3.2), int(T_CLOSE - 0.6), 3): data.blink(_tb + 0.1)   # a long look back still blinks
data.gaze(T_REL + 0.9, 0, 0)
for f in range(F(T_REL), F(T_END) + 1):     # cart rolls on a touch then stops
    sc.frame_set(F(T_PUSH1))
cart_end = Vector(cart["root"].location); cart_rot = cart["root"].rotation_euler.z
for t, dx in ((T_PUSH1, 0.0), (T_PUSH1 + 0.9, 0.22)):
    cart["root"].location = cart_end + Vector((dx, 0, 0)); cart["root"].keyframe_insert("location", frame=F(t))
data.turn_to(-45, T_REL + 0.2, T_REL + 0.9)   # half way: body three-quarter to the lens, the HEAD does the looking back (a full -88 turn left him dead profile, a featureless ball)
sc.frame_set(F(T_REL + 0.9)); _pb = data.pos()
_back = (_pb.x - 0.85, _pb.y - 1.81, 0.72)   # 25 degrees round from the lens toward the lanes: a three-quarter face looking back (65 read as dead profile)
data.look_at(_back, T_REL + 0.9, max_yaw=45)
data.expression("surprised", T_REL + 0.8, T_CLOSE + 0.5)
data.look_at(_back, T_CLOSE - 0.25, max_yaw=45)   # HOLD it: one key let the head drift
data.turn_to(0, T_CLOSE, T_CLOSE + 0.5)            # face -y: the camera (rot 0; 180 faces AWAY: forward = (sin, -cos))
sc.frame_set(F(T_CLOSE + 0.5)); _px = data.pos().x
data.look_at((_px + (CAM_BASE.x - X0), CAM_BASE.y + PUSH_IN, 0.72), T_CLOSE + 0.5)   # into the lens: the camera rides at px + (CAM_BASE.x - X0); a fixed world point turned his head 40 degrees off it
data.act("shrug", T_CLOSE + 0.55, dur=0.25, hold=0.4)   # back to the hang at 9.85 s: the old timing ended at 10.05, so the clip cut out mid-return
data.expression("happy", T_CLOSE + 0.6, T_END)
data.finish()

# ---------------------------------------------------------------- camera: leads him, pushes in at the turn
cam = K.camera(CAM_BASE, CAM_LOOK, lens=LENS, fstop=FSTOP)
for f in range(1, F(T_END) + 1):
    sc.frame_set(f); t = (f - 1) / FPS
    px = Vector(data.arm.location).x
    u_in = ease((t - (T_CLOSE - 0.1)) / 1.2)
    loc = Vector((CAM_BASE.x + (px - X0) + LOOK_AHEAD * min(1, max(0, (t - T_PUSH0) / 0.6)) * (1 - u_in), CAM_BASE.y, CAM_BASE.z))
    look = Vector((px + LOOK_AHEAD, CAM_LOOK.y, CAM_LOOK.z))
    if u_in > 0:
        tgt = Vector((px, 0.0, 0.6)); look = look.lerp(tgt, u_in)
        loc = loc + (tgt - loc).normalized() * PUSH_IN * u_in
    cam.location = loc; cam.keyframe_insert("location", frame=f)
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler(); cam.keyframe_insert("rotation_euler", frame=f)
    cam.data.dof.focus_distance = (Vector((px, 0, 0.5)) - loc).length; cam.data.dof.keyframe_insert("focus_distance", frame=f)

# ---------------------------------------------------------------- look
NYC = os.environ.get("LOOK", "").upper() == "NYC"   # built the way the NYC street was built: real parts, real textures, daylight with a key
if NYC:
    import built; built.apply(sc, store, F(T_END))
style.restyle()
key = style.lights(sc)
if NYC: built.relight(); built.feet_shadow(data)
# beat 3 (losses at self-checkout): while he looks back, every self-checkout's lane lamp goes from green to a blinking red
# and the kiosk terminal screens flash the same red (the lamps alone sit at the top edge of the frame)
for _name, _red, _dim in (("lane lamp", (1.0, 0.08, 0.05, 1.0), (0.25, 0.02, 0.01, 1.0)), ("terminal screen", (1.0, 0.25, 0.2, 1.0), (0.55, 0.12, 0.1, 1.0))):
    _m = bpy.data.materials.get(_name)
    if not (NARR and _m and _m.use_nodes): continue
    _b = _m.node_tree.nodes.get("Principled BSDF")
    if not _b: continue
    _cols = [i for i in (_b.inputs.get("Base Color"), _b.inputs.get("Emission Color")) if i is not None and not i.is_linked]
    _rest = [tuple(i.default_value) for i in _cols]
    for _f in range(1, F(T_END) + 1):
        _t = (_f - 1) / FPS
        on = T_REL + 0.9 <= _t < T_CLOSE + 0.3
        for i, r in zip(_cols, _rest):
            i.default_value = ((_red if int((_t - T_REL) * 2.5) % 2 == 0 else _dim) if on else r); i.keyframe_insert("default_value", frame=_f)
    print("BLINK", _name, len(_cols))
# the self-checkout SCREENS (an image texture) take a red wash through a mix node keyed on/off with the lamps
for _sm in {id(k["screen_mat"]): k["screen_mat"] for k in store["kiosks"]}.values():
    if not (NARR and _sm and _sm.use_nodes): continue
    nt = _sm.node_tree; _b = nt.nodes.get("Principled BSDF")
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'
    mix.inputs[7].default_value = (1.0, 0.1, 0.07, 1.0)          # B (colour)
    n = 0
    for inp in (_b.inputs.get("Emission Color"), _b.inputs.get("Base Color")):
        if inp is None or not inp.is_linked: continue
        src = inp.links[0].from_socket
        if n == 0: nt.links.new(src, mix.inputs[6])               # A (colour)
        nt.links.new(mix.outputs[2], inp); n += 1
    fac = mix.inputs[0]
    for _f in range(1, F(T_END) + 1):
        _t = (_f - 1) / FPS; on = T_REL + 0.9 <= _t < T_CLOSE + 0.3
        fac.default_value = (0.85 if int((_t - T_REL) * 2.5) % 2 == 0 else 0.55) if on else 0.0; fac.keyframe_insert("default_value", frame=_f)
    print("BLINK screen", _sm.name, n)
style.follow_key(key, data, 1, F(T_END))
style.render_settings(sc, SPP, PCT)

# ---------------------------------------------------------------- measure
sc.frame_set(F(3.0)); side = acts.near_side(data, cam)   # measured mid-push: at the last frame he faces the lens and the shoulders tie
mx, mean = acts.arm_bend(data, f0, f1, side)
mxo, meano = acts.arm_bend(data, f0, f1, "R" if side == "L" else "L")
sl = acts.arm_slope(data, f0, f1, side)
sc.frame_set(F(3.0)); d_on = acts.hand_on_bar(data, cart, side)
print(f"DATA={WHO} near_side={side} arm_bend near max={mx:.2f} mean={mean:.2f} | far max={mxo:.2f} mean={meano:.2f} | wrist->bar end@3s={d_on*1000:.1f}mm | arm below horizontal min/mean/max={sl[0]:.1f}/{sl[1]:.1f}/{sl[2]:.1f} deg")
c3 = bpy.data.objects.get("lane3 cashier")
if c3: print(f"lane3 cashier @3s at {tuple(round(v,3) for v in c3.matrix_world.translation)} (counter line y=0.32)")
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
