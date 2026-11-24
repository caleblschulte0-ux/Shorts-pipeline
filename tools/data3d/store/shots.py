"""THE SHOT HARNESS of the 3D shorts: one SHOT PER NARRATION LINE, any story.

A story is a folder, tools/data3d/stories/<name>/: script.json (its lines, slug, title, sources) and shots.py, which
defines shot1() .. shotN() and SHOTS = {1: shot1, ...}. Each shot builds its act and returns a dict: data (the rig),
lanes/kiosks (store fixtures it built, or []), rest (the frame the fixtures are dressed at), conseq (what each thing
Data does CAUSES, measured on screen), grips (what his hands hold on purpose), and optional cutaway / open_roof /
no_blur / framing. The harness does everything a shot must not have to remember: the timing from the voice, the
approved store dressing and lights, and every check, BEFORE a frame renders:
  staging     his face to the lens, and big enough: a medium shot or closer (staging.MIN_H, the 2026-11-12 brief:
              "Avoid wide shots where Data becomes tiny")
  consequence every action shows what it causes
  anatomy     no joint bends the way no body can
  clipping    nothing of him passes through himself or the set
  ending      the last shot ends ON its payoff, never a pull-back to a wide frame
  twitch      no bone whips, no face control pops
  face lint   a worried / alarmed / surprised / sad / wry / determined face never turns into a smile (store/facelint.py)
  steady      faces held, the head at a person's speed and at rest between looks, no leg through the coat (store/steady.py)
  pop / hold  no move jumps between proof frames, glides on planted feet or leaps without air time; no pose held over
              0.8 s (store/motion.py); a fast move's in-between frames go into a proof render (inbetween.json)
  read        his pose changes big enough to see on the judge's phone-sized sheet: no still stretch over 1 s on
              screen, and every strike near him visibly moves him (store/motion.py READ)
  far         at each arc moment he is big, every strike lands near him and reads, a fall is seen from the side; each
              strike's channel is in frame to its target, steep, and off his body unless he is its target
              (staging.far, its rules in store/motion.py FAR and BOLT)
  empty       after the frames render: the set behind him is not one flat, bare region (store/empty.py)
  hands       IK hands re-solved on the final body (character.Data._resolve_hands, in finish(); reported as HANDS)
  storyboard  before any of it, the script's payoffs are carried by big props or actions (store/boardlint.py)

    usage: STORY=name SHOT=n python -I shots.py OUTDIR [SPP] [PCT]
    env: NARR=narration.json | STILL=<local t> | STEP | KEYS=n (n evenly spaced stills: the storyboard pass) | FRAMES=a-b | STAGING=strict|on | CLIPPING=strict|report
Frames are written with GLOBAL numbers (the shot's start in the narration + local frame), so the shot folders merge
into one sequence. Prints 'FRAME n seconds'."""
import sys, os, math, json, time, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import bpy
from mathutils import Vector, Matrix
import scene_kit as K, acts, style, built, props, clock
from acts import ease, ease_out, ease_in, ease_out_back, lerp
from clock import FPS

STORY = os.environ.get("STORY", "checkout")
STORY_DIR = os.path.join(os.path.dirname(HERE), "stories", STORY)
SCRIPT = json.load(open(os.path.join(STORY_DIR, "script.json")))
SHOT = int(os.environ.get("SHOT", "1"))
import boardlint   # the payoff is carried by a big prop or action, never a subtle face or a tiny change (store/boardlint.py)
for _where, _p in boardlint.problems(SCRIPT):
    print(f"BOARD {STORY} {_where}: {_p}" + ("" if boardlint.held(STORY) else
          f" (not binding: {'posted' if STORY in boardlint.POSTED else 'grandfathered, see store/boardlint.py'})"), flush=True)
if boardlint.held(STORY) and boardlint.problems(SCRIPT) and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"{STORY}: the storyboard lint fails: a beat's payoff leans on a subtle face or a tiny change; give it a big prop or action")
import variety    # build fresh, reuse is rare (caaleb 2026-11-18, "lazy as shit"): every beat its own camera, act, props
_vp = variety.script_problems(SCRIPT) + variety.code_problems(open(os.path.join(STORY_DIR, "shots.py")).read(), SCRIPT)
for _where, _p in _vp:
    print(f"VARIETY {STORY} {_where}: {_p}" + ("" if variety.held(STORY) else " (not binding: grandfathered)"), flush=True)
if variety.held(STORY) and _vp and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"{STORY}: the beats repeat each other (store/variety.py): build each beat its own camera, act and props")
import fresh      # every video new, every beat worth watching (caaleb 2026-11-19: "Dr. Katz effect ... reusing backgrounds ... works for maybe 1 second")
import story_world   # story and world first (caaleb 2026-11-19: "Building a world that the viewer has to believe in")
_fp = fresh.problems(STORY, SCRIPT) + story_world.problems(STORY, SCRIPT)
for _where, _p in _fp:
    print(f"FRESH {STORY} {_where}: {_p}", flush=True)
if _fp and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"{STORY}: an old set, an old gag, a one-second beat, a talking head (store/fresh.py) or no world (store/story_world.py): build it new")
import story_gate   # the script is a STORY before a shot is built (caaleb 2026-11-23: "why do our scripts suck")
_sg = story_gate.problems(STORY, SCRIPT)
for _p in _sg:
    print(f"STORY {STORY}: {_p}", flush=True)
if _sg and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"{STORY}: the script is not a story yet (store/story_gate.py): fix the lines, then judge them")
OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/tmp/shots"
SPP = int(sys.argv[2]) if len(sys.argv) > 2 else 24
PCT = int(sys.argv[3]) if len(sys.argv) > 3 else 60

# ---------------------------------------------------------------- timing from the voice
NARR = os.environ.get("NARR")
W = json.load(open(NARR))["windows"] if NARR else SCRIPT["draft_windows"]   # a staging read, near enough until the voice exists
NSHOTS = len(W)
T0, T1, G0, NF = clock.span(W, SHOT)
DUR = NF / FPS
F = clock.F
acts.F = F

sc = bpy.context.scene
for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)
sc.frame_start = 1; sc.frame_end = NF



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
    Front is -Y; yaw turns it. 20:24Z: "they can have arms" -- plain tubes, no hands."""
    root = K.empty(name, loc); L = Vector(loc); s = 1.65 * K.U / 0.924
    body = K.mat("person body", "#2F6FA6", rough=0.6); head = K.mat("person head", "#E2D6CA", rough=0.55); leg = K.mat("person legs", "#33363C", rough=0.6)
    P = lambda ox, oy, oz: Vector((L.x + ox, L.y + oy, L.z + oz * s))
    for sg in (-1, 1):
        K.capsule("leg", P(sg * 0.055, 0, 0.44), P(sg * 0.055, 0, 0.05), 0.05, leg, parent=root)
    t = K.capsule("body", P(0, 0, 0.47), P(0, 0, 0.74), 0.15, body, parent=root, ra=0.13, rb=0.15); t.scale = (1.0, 0.72, 1.0)
    K.sph("head", P(0, 0, 0.9), 0.1, head, scale=(1.0, 1.0, 1.08), parent=root)
    for sg in (-1, 1):   # plain arms: one rounded tube each, hanging a little off the body, no hands
        K.capsule("arm", P(sg * 0.15, 0, 0.72), P(sg * 0.175, -0.015, 0.45), 0.038, body, parent=root)
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


def blink_red(kiosks, t_on, t_off, rate=2.5, alarm=False):
    """every self-checkout's lane lamp and terminal go red and blink; its main screen takes a red wash. alarm=True also
    hangs a red light over each machine that pulses with the blink, so the alarm washes the floor and reads at phone
    size (11-12 judge: "the red screens are blinking but small and dim")"""
    on = lambda t: t_on <= t < t_off
    ph = lambda t: int((t - t_on) * rate) % 2 == 0
    if alarm:
        for i, kk in kiosks.items():
            if not any(o.name.startswith("error text") for o in kk["root"].children_recursive):
                sp = kk["root"].location; zc = 0.9 * K.U * 1.3 + 0.17; nrm = Vector((0, -math.cos(math.radians(18)), -math.sin(math.radians(18))))
                K.text(f"error text {i}", "ERROR", tuple(Vector((sp.x, sp.y - 0.063, zc)) + nrm * 0.008), 0.085, (math.radians(108), 0, 0),
                       K.mat("error ink", "#FFFFFF", rough=0.3, emit=5.0), extrude=0.003, parent=kk["root"])
            r = kk["root"]; ld = bpy.data.lights.new(f"alarm {i}", 'POINT'); ld.color = (1.0, 0.12, 0.08); ld.shadow_soft_size = 0.15
            o = bpy.data.objects.new(f"alarm {i}", ld); o.location = (r.location.x, r.location.y - 0.35, 1.05); bpy.context.collection.objects.link(o)
            for f in range(1, NF + 1):
                t = (f - 1) / FPS; ld.energy = (11.0 if int((t - t_on) * rate + 0.5 * i) % 2 == 0 else 1.5) if on(t) else 0.0   # light FROM each machine, staggered down the row: not a red filter on the frame
                ld.keyframe_insert("energy", frame=f)
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
        es = b.inputs["Emission Strength"]                       # a hard pulse between two REDS: bright, then dim
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; es.default_value = (2.8 if ph(t) else 0.2) if on(t) else 0.9   # 11-12 panel: 2.4/0.9 read as a steady red; ON, then nearly OFF
            es.keyframe_insert("default_value", frame=f)
        for kp in (fc for fc in (nt.animation_data.action.fcurves if nt.animation_data and hasattr(nt.animation_data.action, "fcurves") else [])):
            for k_ in kp.keyframe_points: k_.interpolation = 'CONSTANT'

        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'; mix.inputs[7].default_value = (1.0, 0.1, 0.07, 1.0)
        n = 0
        for inp in (b.inputs.get("Emission Color"), b.inputs.get("Base Color")):
            if inp is None or not inp.is_linked: continue
            src = inp.links[0].from_socket
            if n == 0: nt.links.new(src, mix.inputs[6])
            nt.links.new(mix.outputs[2], inp); n += 1
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; mix.inputs[0].default_value = 1.0 if on(t) else 0.0; mix.inputs[0].keyframe_insert("default_value", frame=f)


def more_panels():
    """the lit ceiling runs the whole width of a ten-lane row"""
    for x in (-4.0, -2.8, 4.4):
        for y in (-0.9, 0.6):
            ld = bpy.data.lights.new(f"panel {x}_{y}", 'AREA'); ld.energy = 12; ld.color = (1.0, 0.97, 0.92); ld.shape = 'RECTANGLE'; ld.size = 1.1; ld.size_y = 0.3
            o = bpy.data.objects.new(f"panel {x}_{y}", ld); o.location = (x, y, 2.45); bpy.context.collection.objects.link(o)
            o.rotation_euler = Vector((0, 0, -1)).to_track_quat('-Z', 'Y').to_euler()


def camera_path(cam, fn, f0=1, f1=None, roll=0.0):
    """fn(t) -> (loc, look, focus_point); roll (degrees) turns the frame about the lens axis"""
    from mathutils import Quaternion
    for f in range(f0, (f1 or NF) + 1):
        t = (f - 1) / FPS; loc, look, foc = fn(t)
        loc = Vector(loc); look = Vector(look)
        cam.location = loc; cam.keyframe_insert("location", frame=f)
        cam.rotation_euler = ((look - loc).to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), math.radians(roll))).to_euler(); cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.dof.focus_distance = (Vector(foc) - loc).length; cam.data.dof.keyframe_insert("focus_distance", frame=f)


def grip_follow(data, side, point_fn, t0, t1, elbow_out=0.5):
    """one hand ON a moving thing every frame (a lever handle, a sack's neck)"""
    for f in range(F(t0), F(t1) + 1):
        t = (f - 1) / FPS; sc.frame_set(f); data._arm_ik(side, Vector(point_fn(t)), t, elbow_out)


def meshes(objs):
    """the visible parts of these things (an empty's children), for the consequence check"""
    out = []
    for o in objs:
        o = o["root"] if isinstance(o, dict) else o
        out += [x for x in [o] + list(o.children_recursive) if x.type in ('MESH', 'FONT')]
    return out


def near_hand(data, p):
    """the rig names its bones from the viewer's side: decide the hand by geometry"""
    sc.frame_set(1); bpy.context.view_layer.update()
    return min("LR", key=lambda s: (acts._shoulder(data, s) - Vector(p)).length)


def load_data():
    import character as CH
    CH.Data.PALM = variety.held(STORY)          # a held story puts his PALM on every job (character.Data.PALM)
    CH.Data.SHOT_LEN = DUR                      # the cut: his last face is held to it (character.face_plan)
    return CH.load(sc)


_story = os.path.join(STORY_DIR, "shots.py")
exec(compile(open(_story).read(), _story, "exec"), globals())   # the story's acts, in this namespace
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920   # portrait WHILE the shot is built: compose.drop_cut and every on-screen measure a shot takes see the real frame, not the 16:9 default
S = SHOTS[SHOT]()
data = S["data"]; sc.frame_start = 1; sc.frame_end = NF
if "sets" in SCRIPT and S.get("place", "store") != SCRIPT["sets"][SHOT - 1]:
    raise SystemExit(f"shot {SHOT} is set in {S.get('place', 'store')!r} but the script puts this beat in {SCRIPT['sets'][SHOT - 1]!r}")
if S.get("place", "store") == "store":     # the approved supermarket and its lamps
    store = {"lanes": S["lanes"], "extra": [], "kiosks": S["kiosks"]}
    built.apply(sc, store, S["rest"])
    style.restyle()
    key = style.lights(sc); more_panels()
    built.relight()
else:                                      # a place of its own (store/locations.py): it brings its own light
    key = S["light"]()
built.feet_shadow(data)
if S.get("open_roof"):   # the camera is up in the roof: take the deck, joists, ducts and pendants out of its way
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.type == 'MESH':
            zmin = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
            if zmin > 2.15:
                win = S["open_roof"]
                if win is True: o.hide_render = True
                else:                         # only while the camera is up there (a cut to the row from above)
                    for f in range(1, NF + 1):
                        o.hide_render = win[0] <= (f - 1) / FPS < win[1]; o.keyframe_insert("hide_render", frame=f)
style.follow_key(key, data, 1, NF)
style.render_settings(sc, SPP, PCT)
if S.get("no_blur"): sc.render.use_motion_blur = False   # a still camera on swapping lanes: blur only smeared the swaps into ghosts (judge)
if os.environ.get("TEMPORAL_SAFE", "1") == "1":
    cy = sc.cycles; cy.adaptive_threshold = 0.01; cy.denoising_prefilter = 'ACCURATE'

import staging    # the filmmaker's check: his face to the lens, big enough to read, MEASURED before a frame renders
if not staging.check(data, sc.camera, NF, name=f"shot {SHOT}", cutaway=S.get("cutaway"), min_h=SCRIPT.get("min_h")) and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails staging: restage it (his back to the lens, or too small to read)")
if not staging.consequence(sc.camera, NF, S.get("conseq", []), name=f"shot {SHOT}") and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the consequence check: what Data does is not shown happening")
if SHOT == NSHOTS and not SCRIPT.get("legacy_ending") and not staging.ending(data, sc.camera, NF, S.get("conseq", []), name=f"shot {SHOT}") \
        and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the ending check: the video must end ON its payoff, never a pull-back")
import compose    # frame-first placement: every declared box (signs, labels, the beat's prop) holds (store/compose.py)
_sysok = [staging.edges(data, sc.camera, NF, name=f"shot {SHOT}", declared=S.get("texts", ())),   # nothing with words cut by the edge; he ends whole
          staging.keys(data, sc.camera, NF, name=f"shot {SHOT}"),                                 # the board's four stills are four pictures
          staging.talking(data, sc.camera, NF, grips=S.get("grips", ()), name=f"shot {SHOT}"),    # not a talking head
          staging.cause(data, NF, S.get("conseq", []), grips=S.get("grips", ()), name=f"shot {SHOT}"),   # nothing moves on its own
          compose.check(sc.camera, NF, S.get("boxes", []), name=f"shot {SHOT}")]
if not all(_sysok) and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails EDGES / KEYS / TALKING / CAUSE / COMPOSE: what the board judge would have caught (2026-11-23)")
import anatomy    # the body check: no joint outside a body's range on any frame (caaleb 2026-11-12: "bending in inhuman ways")
if not anatomy.check(data, NF, name=f"shot {SHOT}") and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the body check: a joint bends the way no body can")
import clipping   # nothing of him passes through himself or the set (caaleb 2026-11-12: "clipping issues when data moves")
CLIP_MODE = os.environ.get("CLIPPING", SCRIPT.get("clipping", "strict"))   # strict for every story but the first, which predates the check
if not clipping.check(data, NF, name=f"shot {SHOT}", grips=S.get("grips", ())) and CLIP_MODE == "strict" \
        and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the clipping check: part of him passes through something")
import twitch     # no whip, no pop (caaleb 2026-11-13: "why does data tweak out"): every bone and face control, per frame
if not twitch.check(data, NF, name=f"shot {SHOT}") and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the twitch check: a bone whips or the face pops in one frame")
import facelint   # a face that is not a smile never turns into one (2026-11-14, saffron shot 4: "the opposite emotion")
if not facelint.check(data, NF, name=f"shot {SHOT}") and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the face lint: a worried / alarmed / sad / wry face smiles inside its own window")
import steady     # ONE real person (caaleb 2026-11-23, lightning: "changing emotions too often ... his head moves really fast
                  # ... his legs are kind of glitching out of his coat"): faces held, head at a person's speed, coat on the legs
if not steady.check(data, NF, name=f"shot {SHOT}") and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the steady check: a face flickers, his head whips or never rests, or a leg pokes through his coat")
import motion     # POP, HOLD and FAR (the lightning rough cut, 2026-11-20: "good not great, clearly there are large scale
                  # issues"): a teleport between proof frames, a pose held two seconds, the event far from him (store/motion.py)
_bind = fresh.held(STORY); _nb = "" if _bind else " (not binding: grandfathered)"
_mo_ok, FAST = motion.check(data, sc.camera, NF, name=f"shot {SHOT}" + _nb, cutaway=S.get("cutaway"))
if not _mo_ok and _bind and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the motion check: a move pops between proof frames or glides, or he holds one pose too long")
_near = [f for _r, f in staging.near_strikes(data, NF, S.get("cutaway"))]   # READ (round 2): his moves big enough to see on
if not motion.read_check(data, sc.camera, NF, _near, name=f"shot {SHOT}" + _nb, cutaway=S.get("cutaway")) and _bind \
        and os.environ.get("STAGING", "strict") == "strict":     # the judge's phone-sized sheet, and every strike moves him
    raise SystemExit(f"shot {SHOT} fails the READ check: on the judge's sheet he holds still too long, or a strike near him does not visibly move him")
_st = SCRIPT.get("staging") or []   # the beat's arc moments (fractions of the beat), where FAR measures him
_arc = [m["at"] for m in (_st[SHOT - 1].get("arc") or []) if isinstance(m, dict) and "at" in m] if len(_st) >= SHOT and isinstance(_st[SHOT - 1], dict) else []
if not staging.far(data, sc.camera, NF, _arc, name=f"shot {SHOT}" + _nb, cutaway=S.get("cutaway")) and _bind \
        and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the FAR check: at an arc moment he is small, or the event lands far from him, or a fall is seen from the front")
if os.environ.get("KEYS"):   # the storyboard pass: the framing fingerprint, compared across beats (store/variety.py)
    os.makedirs(OUT, exist_ok=True)
    _fr = staging.framing(data, sc.camera, NF); print(f"FRAMING shot {SHOT}: {_fr}", flush=True)
    json.dump(_fr, open(os.path.join(OUT, "framing.json"), "w"))
n_res, worst_res = getattr(data, "hands_resolved", (0, 0.0))   # character.Data._resolve_hands, in data.finish()
print(f"HANDS shot {SHOT}: {n_res} IK frames re-solved after a later body move (worst drift {worst_res * 100:.1f} cm) -> OK", flush=True)
os.makedirs(OUT, exist_ok=True)
if os.environ.get("DIAG"): exec(open(os.environ["DIAG"]).read()); sys.exit(0)
still = os.environ.get("STILL"); step = int(os.environ.get("STEP", "1")); fr = os.environ.get("FRAMES")
if still is not None: frames = [min(NF, F(float(still)))]
elif fr: a, b = fr.split("-"); frames = [f for f in range(int(a), int(b) + 1, step) if 1 <= f <= NF]
elif os.environ.get("KEYS"): k = max(2, int(os.environ["KEYS"])); frames = sorted({1 + round((NF - 1) * (0.08 + 0.9 * i / (k - 1))) for i in range(k)})
else: frames = list(range(1, NF + 1, step))
INBETWEEN = []   # a proof samples every STEP-th frame, so a fast move shows as its two ends (the tower's "teleport", judge
                 # 2026-11-20): every frame inside a measured fast move goes into the proof too, and judge3d.strip marks them
if step > 1 and still is None and not os.environ.get("KEYS") and os.environ.get("INBETWEENS", "1") == "1":
    _lo, _hi = (frames[0], frames[-1]) if frames else (1, 0)
    INBETWEEN = sorted({f for a, b in FAST for f in range(a, b + 1) if _lo <= f <= _hi} - set(frames))
    frames = sorted(set(frames) | set(INBETWEEN))
import glob as _glob   # 2026-11-18: an old still of a REWRITTEN shot was silently kept and looked at as the new one
SOURCE_MTIME = max(os.path.getmtime(f) for f in [os.path.join(STORY_DIR, "shots.py"), os.path.join(STORY_DIR, "script.json")]
                   + _glob.glob(os.path.join(HERE, "*.py")) + _glob.glob(os.path.join(os.path.dirname(HERE), "*.py")))
print(f"SHOT {SHOT} T0={T0:.2f} T1={T1:.2f} NF={NF} G0={G0}")
json.dump([G0 + f for f in INBETWEEN], open(os.path.join(OUT, "inbetween.json"), "w"))
from bpy_extras.object_utils import world_to_camera_view as _w2c
_seen = []       # (frame png, Data's box on screen) for the EMPTY check (store/empty.py)
for f in frames:
    path = os.path.join(OUT, f"f{G0 + f:04d}.png")
    sc.frame_set(f); bpy.context.view_layer.update()
    _pp = [_w2c(sc, sc.camera, data.arm.matrix_world @ v) for b in data.arm.pose.bones for v in (b.head, b.tail)]
    _pp = [q for q in _pp if q.z > 0]
    _seen.append((path, (min(q.x for q in _pp), max(q.x for q in _pp), min(q.y for q in _pp), max(q.y for q in _pp)) if _pp else None))
    if os.path.exists(path) and os.path.getmtime(path) > SOURCE_MTIME: continue   # a frame older than the code is stale
    t0 = time.time(); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print(f"FRAME {G0 + f} {time.time() - t0:.1f}", flush=True)
import empty      # the set reads flat and bare (the lightning rough cut: "a flat lawn with cutout pines", "an empty plane")
if not empty.check([(p, b) for p, b in _seen if os.path.exists(p)], name=f"shot {SHOT}" + _nb) and _bind \
        and os.environ.get("STAGING", "strict") == "strict":
    raise SystemExit(f"shot {SHOT} fails the EMPTY check: the set behind him is one flat, bare region; dress it")
