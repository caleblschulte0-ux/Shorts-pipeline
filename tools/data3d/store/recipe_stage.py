"""THE RECIPE, STAGED: given the shot's prop (where it is, how big) and its plan, put Data and the lens where the
shots that passed the board had them, and hand back the four stills' keys (2026-11-26).

Every shot used to start from typed coordinates: a place for him, a yaw, a camera somewhere, and the panel said what
was wrong with the picture those happened to make. The three lava shots that passed (3, 4, 5; 71, 72, 72) were staged
the same way in the end, and their numbers are these:
  the lens   24 mm (store/scene_kit.camera's 36 mm vertical sensor), about a metre and a quarter from him, at chest
             to eye height; a still camera (store/boardlint.py refuses a camera move inside the action)
  his size   0.345, 0.35, 0.42 of the frame height, crown to feet (compose.frame_data `height`)
  his place  face at x 0.24 to 0.38 from his side of the frame, y 0.47 to 0.60: he is on one side, the event on the other
  his turn   chest 20 to 45 degrees off the lens, turned TOWARD the prop: three-quarter, never square-on, never profile
  the prop   beside him or in front of him and a little further from the lens than he is, so it is mid-frame, never
             behind his back and never between him and us
  the stills before (he looks at the prop), action (he leans in, hands on it), result (he recoils, the prop changed),
             reaction (he turns to us): four poses that differ bone by bone (recipe_check.POSE_KIND)

  stage(prop_at, prop_size, ...)   plain math (store/compose.py's Pinhole; no Blender): where he stands, his yaw, the
                                   camera, and the four keys, searched so that he is close (MIN_H or more), the prop
                                   is whole inside the frame (when it is `whole`) and big enough to be the beat's prop
                                   (staging.HERO_MIN_H), his chest is three-quarter and the prop is not behind him.
                                   What it returns passes store/recipe_check.py's CLOSE / FACE / EDGE by construction;
                                   tests/test_data3d_a_shot_is_born_to_the_recipe.py holds that over a spread of props.
                                   "reach": True when the prop is also inside his reach (NEAR, WORK_DEG).
                                   handle=(x, y, z): the place on a tall or wide prop his hand works (a lever, a
                                   rope, a crank); over HAND_HI above his feet it returns a "step" (at, size) the
                                   shot builds and he stands on. travel=(dx, dy): he walks the prop that far with
                                   his hand on it; both ends are inside the frame or it is refused with the sum.
  from_plan(plan_shot, prop_at, prop_size)   the same, read off the shot's plan (store/shot_plan.py)
  place / perform / frame          in Blender, on his rig: stand him there, key the four poses, solve the real camera
                                   on his real body (compose.frame_data) and build it
  stub(story)                      a shots file for a planned story, a few lines a shot, calling these

WHAT perform() IS PROVEN ON (store/recipe_prove.py, tests/data3d_recipe/cases/, proof in tests/data3d_recipe/proof.json).
Seven shots on plain boxes, built through store/shots.py with no render, each held to EVERY check the harness prints
(STAGING, CONSEQUENCE, EDGES, KEYS, TALKING, CAUSE, RECIPE, ANATOMY, CLIPPING, TWITCH, FLUID, REACH, FACE, STEADY,
POP, HOLD, READ, FAR, HANDS), all OK for this file as it is now (the proof carries its fingerprint; a test fails when
the code moves on without a new proof):
  1 a 0.2 m thing he PICKS UP off a stump       perform(pick=True) + carry()
  2 a 0.5 m crate he works with a hand on it    perform(grip=...)
  3 a 0.62 m crate he shoves away from the lens the same; his body follows the grip
  4 a 1.5 m post worked by a lever at his hand  stage(handle=...)
  5 the same lever over his reach               stage(handle=...) gives a "step"; he is planted on it
  6 a small crate he walks 0.22 m across        stage(travel=...); character.walk_to(pushing=True)
  7 a puddle on the ground worked with a stick  perform(tool=True) + carry()
What each number below is there for, each one a check that failed on the way: a key between two frames (a 36
deg/frame arm snap); a hand job from too far (REACH) or from inside the prop (CLIPPING); a body that swayed off a
grip that stayed put (the arm locked straight, then snapped 58 deg in a frame as it bent again); a held thing shown
ahead-and-out of his shoulder (the elbow's bend plane turns over there: the same snap); arm poses under 7 cm apart
(HOLD read "up", "guard", "show" and "high" as one held pose); a step to his side AND back from the lens (they cancel
on screen: KEYS 0.050); "back from the lens" taken along the line from him to it instead of the lens's own axis (his
head at the frame edge); a turn of his chest while his hand was on its way (FLUID's stutter); a face 71 degrees off
the lens on still 1; a step cut by the frame.
WHAT IT IS NOT. The props are boxes on a flat field at one frame size and a 4 s beat (4.6 s for the last): the
margins are thin in places (KEYS 0.052 against 0.05 where the frame has no room beside him; READ 0.90 s against 1.0),
so a real prop can still fail a check and the checks still judge every build. A push longer than the frame holds
(about 0.3 m with a 0.3 m prop at his size) and a push away from the lens are REFUSED by stage() with the sum, not
staged: they are a cut. character.walk_to keys his height from the ground at z 0, so a push on raised ground is not
covered. The prop's own animation is the shot's, checked by CONSEQUENCE, CAUSE and RECIPE as before.

A new story's shot is then:

    def shot3():
        P = place_my_set()                                   # the set and the prop, built from their real parts
        plan = shot_plan.shot(STORY, 3)
        st = recipe_stage.from_plan(plan, prop_at=P["prop"].location, prop_size=(0.5, 0.4, 0.6))
        data = load_data(); recipe_stage.place(data, st)
        recipe_stage.perform(data, st, DUR, grip=lambda t: handle_point(t))     # his hands ON the prop through the action
        ...the prop's own animation: what the action does to it, keyed at st["times"]...
        data.finish(); cam = recipe_stage.frame(data, st, DUR)
        return dict(lanes=[], kiosks=[], place="my_set", light=P["light"], data=data, rest=1, grips=("handle",), cutaway=None,
                    boxes=[], conseq=[("what the action does", [P["prop"]], st["times"]["action"], DUR, {"moves": True})])
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose

KEYS_AT = (0.08, 0.38, 0.68, 0.98)     # store/staging.py KEYS_AT
EVENTS = ("before", "action", "result", "reaction")
LENS = 24.0
DATA_H = 0.69                          # metres, crown to feet
FACE_Z = 0.6                           # his face centre above his feet (the rig's head bone, mid-way)
HALF_W = 0.2                           # half his width with his arms out a little
MIN_H = 0.33                           # the least he stands in the frame (shot_plan.MIN_FRAME_H: a third)
HEIGHTS = (0.42, 0.38, 0.35, 0.345, 0.33)   # tried in this order: the passing shots' sizes, biggest first
FACE_X = (0.30, 0.26, 0.34, 0.22)      # his face from HIS side of the frame (lava 3-5: 0.24 to 0.38)
FACE_Y = 0.55
FACE_YS = (0.55, 0.47)                 # his face up the frame (lava 3-5: 0.47 to 0.60); the lower one leaves headroom for a tall prop
HAND_Z = 0.36                          # metres over his feet his hand works at without a stoop or a stretch
HAND_HI = 0.5                          # a handle higher than this over his feet is over his reach: he stands on a step
STEP_YS = (0.62, 0.58)                 # his face up the frame when he stands on a step: higher, so the step under him is whole in it
STEP_W = 0.34                          # metres square, the step he stands on
CLEAR = 0.13                           # metres from his middle to a prop's face, at least: his coat is clear of it
THREE_Q = (35.0, 28.0, 42.0, 50.0)           # degrees his chest is turned off the lens toward the prop
NEAR_STEP = (0.15, 0.21)               # the same from a step, where his feet stay put: inside his arm's length as he stands
NEAR = (0.2, 0.3)                      # metres from him to the face of a prop he works on: clear of his coat, inside his reach
WORK_DEG = 62.0                        # degrees the prop is round from his chest, at most: further and his arm goes behind his back
GAP = 0.3                              # metres between him and the prop's side
HERO_PAD = 0.01                        # of the frame, over HERO_MIN_H: the measured prop is its mesh, a little under its box
PAD = 0.03                             # of the frame: a whole prop stays this far inside the edges
HERO_MIN_H = 0.25                      # store/staging.py HERO_MIN_H: the beat's prop is a quarter of the frame or more
EVENT_X = (0.42, 0.9)                  # where a field-wide thing's focus sits across the frame, from his side
EVENT_Y = (0.2, 0.75)
SQUARE_DEG, BEHIND_DEG = 20.0, 120.0   # store/recipe_check.py: square-on to the lens; behind his back
CHEST_MAX = 50.0                       # his chest off the lens as he stands (lava 3-5 at the stills: 17 to 46, once 78 walking in)
FACE_LIMIT = 60.0                      # his face off the lens on a still, at most (the passing shots: up to 61; recipe_check.FACE_MAX is 70)
FACE_TURN = 25.0                       # his head turns this far past his chest toward the prop
ARM_OF = {"before": "ready", "action": "work", "result": "whoa", "reaction": "up"}
SPINE_OF = {"before": 6.0, "action": 4.0, "result": -14.0, "reaction": -4.0}
TIMES = {"before": 0.0, "action": 0.30, "release": 0.50, "result": 0.64, "reaction": 0.88}   # of the beat: each has landed by its still


# the beat's moves, as shares of its length: each lands before its still (KEYS_AT) and runs into the next, so no
# stretch is a held pose (store/motion.py HOLD: 0.8 s) and every second moves him on the judge's sheet (READ)
PAUSE = 0.1                            # seconds he holds the recoil before he turns to us
STAND_OFF = (0.36, 0.33, 0.3, 0.27, 0.24, 0.21, 0.18)   # metres he stands back from the grip: the furthest his shoulder still reaches from
PALM = 0.02                            # metres his palm sits proud of the face it is on
CLEAR_S = 0.18                         # metres from his middle to the prop's footprint as he works: his knees and shoes are clear of it
TAIL = 1.0                             # seconds past the beat he is keyed for: the last shot of a video runs on after its line
ARRIVE = LEAD = 0.9                    # seconds: his hand takes this long to go to the job (0.7 ran the arm at 21.8 deg/frame, FLUID's limit is 22), and he is turned to it by the time it starts: one thing turns at a time (twitch.py's stutter)
TALL = 0.52                            # a prop over this is over his shoulders, at his head: he works it from further back, shoulder on (CLEAR_TALL)
CLEAR_TALL = 0.25
REACH_D = 0.165                        # metres, shoulder to the job (character.reach: about 0.18 is the arm's length)
WALK_DEEP = 0.12                       # and from further from the lens
WALK_IN = 0.05                         # metres he starts further off and walks in
BRACE = 0.06                           # metres his knees bend as he works (lava shot 3: 0.07), and again as he lands the reaction
SWAY = 0.08                            # metres his weight shifts to us and back as he works, so the work reads (motion.py READ)
PUSH_MAX = 100.0                       # degrees off the lens he may walk as he pushes (his head turns to us: PUSH_HEAD); more is his back
PUSH_HEAD = 60.0                       # degrees his head turns to the lens as he walks across it (store/checkout.py: 52)
CHEST_WORK = 56.0                      # degrees his chest may turn off the lens to face the job (his head makes up the rest: FACE_LIMIT)
SHOW_OUT, SHOW_SIDE, SHOW_UP, SHOW_RISE = 0.14, -0.02, -0.07, 0.05   # metres from his shoulder, in HIS frame, his hand shows a thing he picked up: ahead, a little IN toward his chest, down (inside his arm's length; and off the line ahead-and-out, where the elbow's bend plane turns over: a 58 deg/frame snap), and its lift at the reaction
PICK_S = 0.2                           # seconds his hand is on a thing before it comes away in it
HOLD_MOVE = 0.12                       # metres the grip may travel in his hand: he stands and works, a longer push is acts.push
SIDE_MIN = 0.05                        # metres: a step to his side smaller than this is no move on the sheet
BEND = 0.45                            # seconds before the action his knees start to bend to the job
DEEP = 0.22                            # metres he steps straight back from the lens at the result when the frame has no room beside him (under GLIDE's 0.25)
ROOMY = 0.1                            # metres of frame beside him that a sideways recoil needs
RECOIL = 0.14                          # metres he steps back at the result
TO_LENS = (0.14, 0.08)                 # metres he steps back to the middle of the frame and to us at the reaction


def _unit(v):
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


def _box_pts(at, size):
    x, y, z = at; w, d, h = size
    return [(x + sx * w / 2, y + sy * d / 2, z + sz * h) for sx in (-1, 1) for sy in (-1, 1) for sz in (0, 1)]


def _angle(a, b):
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
    return math.degrees(math.acos(dot))


def stage(prop_at, prop_size, side="left", stands="beside", frame_h=None, view_az=0.0, whole=True, focus=None, cam_h=0.5, lens=LENS, handle=None, travel=None):
    """_stage() with the prop inside his reach when the frame allows it ("reach": True: perform() can put his hand on
    it), else the same recipe with the prop beside him out of reach ("reach": False: a prop taller than about a metre
    is framed with him nearer the lens than it; he works it with a tool, a throw or a walk the shot keys itself)"""
    st = _stage(prop_at, prop_size, side, stands, frame_h, view_az, whole, focus, cam_h, lens, reach=True, handle=handle, travel=travel)
    if not st["ok"] and handle is None and travel is None:
        st = _stage(prop_at, prop_size, side, stands, frame_h, view_az, whole, focus, cam_h, lens, reach=False)
    return st


def _stage(prop_at, prop_size, side="left", stands="beside", frame_h=None, view_az=0.0, whole=True, focus=None, cam_h=0.5, lens=LENS, reach=True, handle=None, travel=None):
    """where he stands, his yaw, the camera and the four keys for a prop at prop_at (x, y, its foot's z) of prop_size
    (across, deep, tall; metres). side: which side of the frame HE is on. view_az: the way the lens looks, degrees
    round from +Y (0 looks along +Y, 90 along +X). whole=False: the thing runs past the frame by design; `focus` (a
    world point, default the prop's near foot) is where the event happens and sits mid-frame. Returns a dict; "ok"
    False and "why" when no staging fits (the prop is too big to be whole beside him: come closer to less of it)."""
    px, py, pz = (float(v) for v in prop_at); w, d, h = (float(v) for v in prop_size)
    # A HANDLE: the place on the prop his hand works (a lever, a rope, a crank, a door's handle), a world point. A prop
    # too tall or too wide to be worked by its face is worked by its handle, and he is staged within reach of THAT. A
    # handle above his reach (HAND_HI over his feet) puts him on a STEP of the height that brings it to his hand: the
    # shot builds the step where the staging says ("step": at, size) and he stands on it, planted, for the whole beat.
    # A PUSH: travel = (dx, dy), the way the prop goes with his hand on it, further than a planted hand carries it
    # (HOLD_MOVE). He WALKS with it on stepped feet (character.walk_to), so he and the prop are staged inside the frame
    # at both ends. The frame at the recipe's size is about 1.2 m across (9:16, him a third of its height): a 0.3 m
    # prop has room for about 0.3 m; a push longer than the frame holds is refused with the sum, and is a cut.
    tv = (float(travel[0]), float(travel[1])) if travel is not None else None
    step_h = 0.0
    if handle is not None:
        handle = tuple(float(v) for v in handle)
        if handle[2] - pz > HAND_HI:
            step_h = round(handle[2] - pz - HAND_Z, 2)
    az = math.radians(view_az); v = (math.sin(az), math.cos(az))            # the lens looks along v
    C = (-v[0], -v[1])                                                     # toward the lens
    R = (v[1], -v[0])                                                      # screen right (compose.Pinhole.right)
    s = -1.0 if side == "left" else 1.0                                    # he is on this side of the frame
    half_across = (abs(R[0]) * w + abs(R[1]) * d) / 2                      # the prop's half extent across the screen
    half_deep = (abs(C[0]) * w + abs(C[1]) * d) / 2
    prop_pts = _box_pts((px, py, pz), (w, d, h))
    heights = [frame_h] if frame_h else list(HEIGHTS)
    ex, ey = (px, py) if whole or focus is None else (float(focus[0]), float(focus[1]))     # where the event is
    base = (half_across + GAP) if whole else 0.6
    fwds = (0.1, -0.25, 0.45, -0.6, 0.9, 1.5, 2.3) if stands == "beside" else (0.45, 0.9, 0.1, 1.5, 2.3, -0.25)
    fwds = [f_ + (half_deep if whole and f_ > 0.2 else 0.0) for f_ in fwds]      # further from the lens than he is: clear of its depth
    tried = 0; why = "nothing tried"; whys = {}
    for hgt in heights:
        if hgt < MIN_H:
            why = f"he would stand {hgt} of the frame (min {MIN_H})"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
        for fwd in fwds:
            for lat in sorted({round(max(0.45, 0.5 * fwd), 3), round(max(base, 0.5 * fwd), 3), round(half_across + 0.14, 3), round(half_across + 0.2, 3), round(half_across + 0.26, 3), round(max(base, 0.5 * fwd) + 0.2, 3), round(max(base, 0.5 * fwd) + 0.5, 3)}):
                for fx, fy in [(a_, b_) for b_ in ((STEP_YS + FACE_YS) if step_h else FACE_YS) for a_ in FACE_X]:
                    for tq in THREE_Q:
                        tried += 1
                        D = (ex + R[0] * s * lat + C[0] * fwd, ey + R[1] * s * lat + C[1] * fwd, pz + step_h)
                        tr = math.radians(tq)
                        f = _unit((C[0] * math.cos(tr) - s * R[0] * math.sin(tr), C[1] * math.cos(tr) - s * R[1] * math.sin(tr)))
                        face = (D[0], D[1], D[2] + FACE_Z); crown = (D[0], D[1], D[2] + DATA_H); foot = D
                        cam0 = (D[0] + C[0] * 2.0, D[1] + C[1] * 2.0, D[2] + cam_h)
                        look0 = (cam0[0] + v[0], cam0[1] + v[1], cam0[2])
                        face_at = (fx if side == "left" else 1 - fx, fy)
                        cl, lk, rep = compose.solve_camera(face, crown, foot, cam0, look0, lens, face_at, hgt)
                        if not rep["ok"]:
                            why = "the camera solve did not converge"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        pin = compose.Pinhole(cl, lk, lens)
                        to_cam = _unit((cl[0] - D[0], cl[1] - D[1]))
                        chest = _angle(f, to_cam)
                        near = (min(max(D[0], px - w / 2), px + w / 2) - D[0], min(max(D[1], py - d / 2), py + d / 2) - D[1]) if whole else (ex - D[0], ey - D[1])
                        clear = math.hypot(min(max(D[0], px - w / 2), px + w / 2) - D[0], min(max(D[1], py - d / 2), py + d / 2) - D[1])
                        if handle is not None:
                            near = (handle[0] - D[0], handle[1] - D[1])
                            if clear < CLEAR:
                                why = f"he would stand inside the prop to reach its handle ({clear:.2f} m off its face, {CLEAR} at least)"; whys[why.split("(")[0][:60]] = (whys.get(why.split("(")[0][:60], (0, why))[0] + 1, why); continue
                        bearing = _angle(f, _unit(near)) if math.hypot(*near) > 0.05 else 0.0
                        if not SQUARE_DEG < chest <= CHEST_MAX:
                            why = f"his chest would be {chest:.0f} degrees off the lens"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        nr = NEAR_STEP if step_h else NEAR             # on a step he cannot shuffle in: he is staged where his hand already reaches
                        if reach and (whole or handle is not None) and (not nr[0] <= math.hypot(*near) <= nr[1] or bearing > WORK_DEG):
                            why = (f"his hands would not reach the prop from where he stands ({math.hypot(*near):.2f} m off its face, {bearing:.0f} degrees round "
                                   f"from his chest; {NEAR[0]} to {NEAR[1]} m and {WORK_DEG:.0f} degrees at most)"); whys[why.split("(")[0][:60]] = (whys.get(why.split("(")[0][:60], (0, why))[0] + 1, why); continue
                        if bearing >= BEHIND_DEG:
                            why = "the prop would be behind his back"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        him = [pin.project((D[0] + R[0] * a, D[1] + R[1] * a, D[2] + z)) for a in (-HALF_W, HALF_W) for z in (0.0, DATA_H)]
                        if any(not (PAD <= q[0] <= 1 - PAD and 0.0 <= q[1] <= 1.0) for q in him):
                            why = "he would be cut by the frame edge"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        if step_h:                     # the step he stands on is a thing in the picture: whole, like the prop
                            sb, sfront = compose.bbox(pin.project, _box_pts((D[0], D[1], pz), (STEP_W, STEP_W, step_h)))
                            if not sfront or not compose.inside(sb, (0.005, 0.005, 0.995, 0.995)):
                                why = "the step he stands on would be cut by the frame edge"; whys[why[:60]] = (whys.get(why[:60], (0, why))[0] + 1, why); continue
                        b, front = compose.bbox(pin.project, prop_pts)
                        if tv is not None:
                            off_lens = _angle(_unit(tv), to_cam)
                            if off_lens > PUSH_MAX:
                                why = f"he would turn his back to push it that way ({off_lens:.0f} degrees off the lens, {PUSH_MAX:.0f} at most): push it across the frame"; whys[why.split("(")[0][:60]] = (whys.get(why.split("(")[0][:60], (0, why))[0] + 1, why); continue
                            b2, front2 = compose.bbox(pin.project, _box_pts((px + tv[0], py + tv[1], pz), (w, d, h)))
                            him2 = [pin.project((D[0] + tv[0] + R[0] * a, D[1] + tv[1] + R[1] * a, D[2] + z)) for a in (-HALF_W, HALF_W) for z in (0.0, DATA_H)]
                            if not front2 or not compose.inside(b2, (PAD, PAD, 1 - PAD, 1 - PAD)) or any(not (PAD <= q[0] <= 1 - PAD and 0.0 <= q[1] <= 1.0) for q in him2):
                                why = (f"a push of {math.hypot(*tv):.2f} m does not fit: the frame is about {DATA_H / hgt * 9 / 16:.1f} m across at his size and "
                                       f"he ({2 * HALF_W} m) and the prop ({max(w, d)} m) must be inside it at both ends: push a shorter way, or cut to where it went"); whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        if whole:
                            if not front or not compose.inside(b, (PAD, PAD, 1 - PAD, 1 - PAD)):
                                why = (f"the prop ({w} x {d} x {h} m) would be cut by the frame edge beside him at {hgt} of the frame: "
                                       f"come closer to less of it, or declare it whole: False and name where the event happens"); whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                            if b[3] - b[1] < HERO_MIN_H + HERO_PAD and h >= 0.2:
                                why = f"the prop would be {b[3] - b[1]:.2f} of the frame (the beat's prop is {HERO_MIN_H} or more)"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                            hx0, hx1 = min(q[0] for q in him), max(q[0] for q in him)
                            if min(b[2], hx1) - max(b[0], hx0) > 0.6 * (b[2] - b[0]) and min(q[2] for q in [pin.project(p) for p in prop_pts]) > pin.project(face)[2]:
                                why = "he would stand in front of most of the prop"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        else:
                            fp = (ex, ey, (focus[2] if focus is not None and len(focus) > 2 else pz + 0.3))
                            q = pin.project(fp); ex = q[0] if side == "left" else 1 - q[0]
                            if q[2] <= 0 or not (EVENT_X[0] <= ex <= EVENT_X[1] and EVENT_Y[0] <= q[1] <= EVENT_Y[1]):
                                why = "the place the event happens would not be mid-frame beside him"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        def yaw_at(c):                  # his yaw with his chest c degrees off the lens, turned toward the prop
                            cr = math.radians(c); rp = (-to_cam[1], to_cam[0])
                            g = (to_cam[0] * math.cos(cr) - s * rp[0] * math.sin(cr), to_cam[1] * math.cos(cr) - s * rp[1] * math.sin(cr))
                            return math.degrees(math.atan2(g[0], -g[1]))            # character.Data.forward: (sin yaw, -cos yaw)
                        yaw = math.degrees(math.atan2(f[0], -f[1]))
                        away = _unit((D[0] - ex, D[1] - ey)) if (not whole and handle is None) or math.hypot(*near) < 0.05 else _unit((-near[0], -near[1]))
                        gx, gy = ((D[0] + near[0] + away[0] * PALM, D[1] + near[1] + away[1] * PALM) if whole else (ex, ey))     # on its face nearest him
                        grab = (gx, gy,
                                (focus[2] if focus is not None and len(focus) > 2 else pz + min(0.7 * h, 0.36)))
                        if handle is not None:
                            grab = handle
                        chests = (chest, min(chest + 12.0, CHEST_MAX + 5.0), max(SQUARE_DEG + 2.0, chest - 6.0), SQUARE_DEG + 2.0)
                        steps = ((0.0, 0.0), (-away[0] * 0.05, -away[1] * 0.05), (away[0] * 0.1, away[1] * 0.1), (away[0] * 0.1, away[1] * 0.1))
                        keys = [{"event": e, "at": KEYS_AT[i], "yaw": yaw if i == 0 else _toward(yaw, yaw_at(chests[i]), 1.0), "chest": chests[i], "step": steps[i],
                                 "looks": "lens" if e == "reaction" else "prop", "head": 3.0 if e == "reaction" else max(4.0, min(FACE_TURN, FACE_LIMIT - chests[i])),
                                 "arms": ARM_OF[e], "spine": SPINE_OF[e]} for i, e in enumerate(EVENTS)]
                        return {"ok": True, "why": "", "side": side, "stands": stands, "data_at": D, "yaw": yaw, "cam": cl, "look": lk, "lens": lens,
                                "face_at": face_at, "frame_h": hgt, "chest_deg": chest, "bearing": bearing, "prop_box": b, "prop_at": (px, py, pz),
                                "prop_size": (w, d, h), "grab": grab, "keys": keys, "times": dict(TIMES), "tried": tried, "whole": whole,
                                "reach": bool(reach and (whole or handle is not None)), "handle": handle, "travel": tv,
                                "room": round(((min(q[0] for q in him) if side == "left" else 1 - max(q[0] for q in him)) - PAD) * (DATA_H / hgt) * 9 / 16, 3),
                                "step": ({"at": (D[0], D[1], pz), "size": (STEP_W, STEP_W, step_h)} if step_h else None)}
    if whys:                                     # the reason most of the candidates fell to, not the last one tried
        why = max(whys.values())[1]
        push = [t for _n, t in whys.values() if t.startswith(("a push of", "he would turn his back to push"))]
        if tv is not None and push:
            why = push[0]                            # a push that does not fit says so, whatever else also failed
    return {"ok": False, "why": why, "tried": tried, "side": side, "stands": stands, "whys": sorted(((n, t) for n, t in whys.values()), reverse=True)}


def _toward(a, b, k):
    """yaw a turned a share k of the way to yaw b, the short way round (degrees)"""
    d = (b - a + 180.0) % 360.0 - 180.0
    return a + d * k


def from_plan(plan_shot, prop_at, prop_size, view_az=0.0, focus=None, cam_h=0.5, handle=None, travel=None):
    """stage() read off a shot's plan (store/shot_plan.py): his side, where he stands, his size, whether the prop is whole"""
    d = plan_shot.get("data") or {}
    prop = next((p for p in plan_shot.get("props") or [] if p.get("name") == plan_shot.get("prop")), {})
    st = stage(prop_at, prop_size, side=d.get("side", "left"), stands=d.get("stands", "beside"), frame_h=None, view_az=view_az,
               whole=bool(prop.get("whole", True)), focus=focus, cam_h=cam_h, handle=handle, travel=travel)
    if st["ok"] and isinstance(d.get("frame_h"), (int, float)) and d["frame_h"] >= MIN_H:
        want = stage(prop_at, prop_size, side=d.get("side", "left"), stands=d.get("stands", "beside"), frame_h=float(d["frame_h"]),
                     view_az=view_az, whole=bool(prop.get("whole", True)), focus=focus, cam_h=cam_h, handle=handle, travel=travel)
        if want["ok"]:
            st = want
    return st


def facts(st, dur=4.0, fps=30):
    """the staging as store/recipe_check.py facts (his nominal body, the prop's box), so the staging can be held to the
    measured rules with no Blender: his size, his chest and face to the lens and the prop's box on each of the four stills"""
    pin = compose.Pinhole(st["cam"], st["look"], st["lens"])
    px, py, pz = st["prop_at"]; w, d, h = st["prop_size"]
    stills = []
    for k in st["keys"]:
        D = (st["data_at"][0] + k["step"][0], st["data_at"][1] + k["step"][1], st["data_at"][2])
        yr = math.radians(k["yaw"]); f = (math.sin(yr), -math.cos(yr))
        to_cam = _unit((st["cam"][0] - D[0], st["cam"][1] - D[1]))
        top = pin.project((D[0], D[1], D[2] + DATA_H)); foot = pin.project(D)
        b, front = compose.bbox(pin.project, _box_pts((px, py, pz), (w, d, h)))
        near = (min(max(D[0], px - w / 2), px + w / 2) - D[0], min(max(D[1], py - d / 2), py + d / 2) - D[1])
        face = _angle(f, to_cam) + k["head"] if k["looks"] == "prop" else k["head"]
        stills.append({"at": k["at"], "frame": int(round(k["at"] * (dur * fps - 1))) + 1, "cutaway": False,
                       "data": {"h": round(abs(top[1] - foot[1]), 4), "face_deg": round(face, 1), "chest_deg": round(_angle(f, to_cam), 1)},
                       "prop": {"drawn": 1, "box": [round(x, 4) for x in b], "all_front": front, "centre": [px, py, pz + h / 2], "dims": [w, d, h],
                                "bearing": round(_angle(f, _unit(near)), 1) if math.hypot(*near) > 0.05 else None}})
    return stills


# ------------------------------------------------------------------ in Blender, on his rig

# his arms at each of the four events, as (arm, fore, hand) Euler degrees for the side with sign sg: lava shot 3's
# three poses (LOW, WHOA, UP: braced, flung out, both up) and a reach toward the prop for the action
ARMS = {
    "ready": lambda sg: ((-2, 0, -sg * 26), (-38, 0, -sg * 16), (-10, sg * -30, -sg * 10)),
    "work": lambda sg: ((-46, 0, -sg * 8), (-30, 0, -sg * 10), (-6, sg * -10, -sg * 6)),
    "whoa": lambda sg: ((-16, 0, -sg * 18), (-20, 0, -sg * 40), (-10, sg * -12, -sg * 15)),
    "up": lambda sg: ((-58, 0, -sg * 12), (-48, 0, -sg * 22), (-10, sg * -12, -sg * 15)),
    "high": lambda sg: ((-62, 0, -sg * 10), (-40, 0, -sg * 16), (-8, sg * -10, -sg * 8)),      # a tool in the hand, lifted at the reaction
    "prod": lambda sg: ((-30, 0, -sg * 6), (-8, 0, -sg * 6), (-4, sg * -8, -sg * 4)),          # the tool driven down at the thing on the ground
    "drop": lambda sg: ((-30, 0, -sg * 6), (-8, 0, -sg * 6), (-4, sg * -8, -sg * 4)),          # both hands dropped low in front of him: he has let go; and the low beat of the cheer
}


def place(data, st):
    """stand him where the staging says, feet on the prop's ground"""
    x, y, z = st["data_at"]
    data.place(x, y, st["yaw"]); data.arm.location.z = z
    return data


def perform(data, st, dur, grip=None, faces=("alarmed", "pleased"), ground_z=None, pick=False, tool=False):
    """key the four events on his whole body, one move running into the next so no stretch of the beat is a held pose:
    he walks in looking at the prop (before); at the action he is at the prop with his near hand ON grip(t) (a callable
    t -> world point, or a point; he walks with it while it moves) and leans through it; at the result he lets go and
    recoils a step; at the reaction he turns to the lens, steps to us and throws both arms up. Feet planted on every
    frame. Returns the times {before, action, release, result, reaction}. Call before data.finish().
    pick=True   the grip is a small thing he PICKS UP at the action and keeps: his hand goes to it and never lets go;
                call carry(data, [its objects], T) after data.finish() and it rides in his hand to the end.
    tool=True   he has a tool in his near hand from the first frame (a stick, a hose, a bucket) and works with THAT:
                no hand goes to the prop; call carry(data, [the tool], T) after data.finish().
    A staging with a "step" (a handle over his reach) keeps him planted on it: he shifts his weight, he never walks.
    A staging with a "travel" is a PUSH: from the action to the release he walks that way on stepped feet with his hand
    on the grip, which goes with him; T["moved"](t) is how far the prop has gone at t (a Vector): key the prop by it."""
    from mathutils import Vector
    import acts
    fps = getattr(acts, "FPS", None) or __import__("clock").FPS
    T = {k: round(v * dur * fps) / fps for k, v in st["times"].items()}      # on a frame: a key between two frames bends both
    # the reaction lands on a beat of the cheer that puts "up" on still 4, as soon after the result as the move back takes
    t4 = KEYS_AT[3] * dur; r0 = max(T["result"] + PAUSE + 0.7, T["release"] + 0.9)
    m = max(1, int(round((t4 - r0) / (2 * 0.36))))
    CHEER = (t4 - r0) / (2 * m) if t4 - r0 >= 2 * m * 0.26 else 0.36
    T["reaction"] = round((t4 - 2 * m * CHEER if t4 - r0 >= 2 * m * 0.26 else t4) * fps) / fps; R_ = T["reaction"]; T["end"] = dur
    x0, y0, z0 = st["data_at"]; z0 = z0 if ground_z is None else ground_z
    ks = st["keys"]
    grab = Vector(st["grab"]); cam = Vector(st["cam"])
    fn = None if grip is None or tool else (grip if callable(grip) else (lambda t, p=Vector(grip): p))
    planted = bool(st.get("step"))
    k_walk, k_recoil, k_mid = ((0.0, 0.0, 0.0) if planted else (WALK_IN, RECOIL, TO_LENS[0]))
    if fn and (Vector(fn(T["action"])) - Vector((x0, y0, fn(T["action"])[2]))).length > NEAR[1] + 0.12:
        print(f"STAGE: the grip is {(Vector(fn(T['action'])) - Vector((x0, y0, fn(T['action'])[2]))).length:.2f} m from where he stands: out of his reach, so perform() "
              f"keys no hand on it (stage a prop he can stand at, or key the tool, the throw or the walk in the shot)", flush=True)
        fn = None
    g0 = Vector(fn(T["action"])) if fn else grab
    away = Vector((x0 - g0.x, y0 - g0.y, 0.0)); away = away.normalized() if away.length > 1e-6 else Vector((0, -1, 0))
    lens = Vector((cam.x - x0, cam.y - y0, 0.0)).normalized()
    D = Vector((x0, y0, 0.0))

    def stand(off):                                   # where he stands `off` metres back from the grip, on his own side
        return Vector((g0.x, g0.y, 0.0)) + away * off

    def yaw_to(P, target, limit):          # his yaw at P with his chest toward target, never more than `limit` degrees off the lens
        to_l = Vector((cam.x - P.x, cam.y - P.y, 0.0)).normalized(); to_t = Vector((target.x - P.x, target.y - P.y, 0.0))
        if to_t.length < 1e-6: return ks[1]["yaw"]
        to_t.normalize(); ang = math.degrees(math.atan2(to_l.x * to_t.y - to_l.y * to_t.x, to_l.dot(to_t)))
        ang = max(-limit, min(limit, ang)); a = math.radians(ang)
        f_ = Vector((to_l.x * math.cos(a) - to_l.y * math.sin(a), to_l.x * math.sin(a) + to_l.y * math.cos(a), 0.0))
        return math.degrees(math.atan2(f_.x, -f_.y))

    ppx, ppy, _ppz = st["prop_at"]; pw, pd, _ph = st["prop_size"]
    clear = lambda P: math.hypot(min(max(P.x, ppx - pw / 2), ppx + pw / 2) - P.x, min(max(P.y, ppy - pd / 2), ppy + pd / 2) - P.y)   # his middle to the prop's footprint
    side = None; off = min(STAND_OFF[0], (D - Vector((g0.x, g0.y, 0.0))).length)
    if tool:                                          # the hand nearer the prop has the tool
        data.sc.frame_set(1)
        d = {sd: ((data.arm.matrix_world @ data.pb[f"arm.{sd}"].head) - g0).length for sd in "LR"}
        side = min(d, key=d.get)
    if fn and planted:
        data._kobj(T["action"], loc=(x0, y0, z0), rot=math.radians(yaw_to(D, g0, CHEST_WORK))); data.sc.frame_set(int(round(T["action"] * fps)) + 1)
        d = {sd: ((data.arm.matrix_world @ data.pb[f"arm.{sd}"].head) - g0).length for sd in "LR"}
        side = min(d, key=d.get); off = (D - Vector((g0.x, g0.y, 0.0))).length
    elif fn:                                            # the hand whose shoulder is nearer does the job, from as far back as it reaches
        near_d = (D - Vector((g0.x, g0.y, 0.0))).length
        for off in [o for o in STAND_OFF if o <= near_d + 0.02] or [near_d]:        # never further out than the staging has him: that is past his edge of the frame
            S = stand(off)
            data._kobj(T["action"], loc=(S.x, S.y, z0), rot=math.radians(yaw_to(S, g0, CHEST_WORK))); data.sc.frame_set(int(round(T["action"] * fps)) + 1)
            d = {sd: ((data.arm.matrix_world @ data.pb[f"arm.{sd}"].head) - g0).length for sd in "LR"}
            side = min(d, key=d.get)
            if d[side] <= REACH_D or clear(stand(off - 0.03)) < (CLEAR_TALL if _ph > TALL and g0.z - z0 < _ph - 0.05 else CLEAR_S): break       # as far back as his shoulder reaches from, never into the prop
    S = D if planted else stand(off) if fn else D + (Vector((g0.x, g0.y, 0.0)) - D).normalized() * min(0.08, (Vector((g0.x, g0.y, 0.0)) - D).length * 0.3)
    yaw_act = yaw_to(S, g0, CHEST_WORK) if (fn or tool) else ks[1]["yaw"]       # his chest to the job, as far as his face stays to us
    tv = Vector((st["travel"][0], st["travel"][1], 0.0)) if st.get("travel") and fn and not planted else None
    sm = lambda u: u * u * (3 - 2 * u)
    if fn and tv is None and d[side] > REACH_D + 0.015:
        print(f"STAGE: his {side} shoulder is {d[side]:.2f} m from the grip at the action (his arm is about 0.18): the hand will be short of it (REACH); "
              f"move the grip to the face of the prop nearest him, or give the prop a handle", flush=True)
    if tv is not None:                               # the prop goes with HIM: the grip is a point he carries along his walk
        grip0 = Vector(g0)
        walked = lambda t: tv * max(0.0, min(1.0, (t - T["action"]) / (T["release"] - T["action"])))     # replaced by his real walk below
        fn = lambda t: grip0 + T["moved"](t)
        T["moved"] = walked
    gd = lambda t: (Vector(fn(min(t, T["release"]))) - g0) if fn and tv is None else Vector((0, 0, 0))
    if tv is None and gd(T["release"]).length > HOLD_MOVE:
        print(f"STAGE: the grip travels {gd(T['release']).length:.2f} m in his hand (perform() stands and works: {HOLD_MOVE} m at most; "
              f"a longer push is acts.push or walk_to)", flush=True)
    G = lambda t: Vector((gd(t).x, gd(t).y, 0.0))    # the way the grip has gone in his hand: his body goes with it, so the hand stays in reach
    GR = G(T["release"])
    S2 = S + (tv if tv is not None else GR)                                    # where he is when he lets go
    # the SCREEN's own axes (the way the lens looks, not the line from him to it: he stands off its axis, and a step
    # "back from the lens" along that line is also a step toward his edge of the frame)
    ax = Vector((st["look"][0] - cam.x, st["look"][1] - cam.y, 0.0)); ax = ax.normalized() if ax.length > 1e-6 else -lens
    to_us = -ax
    cross = Vector((ax.y, -ax.x, 0.0)) * (-1.0 if st.get("side", "left") == "left" else 1.0)      # across the screen, to his own side
    # he recoils to his own side only as far as the frame has room for him (st["room"]: the staging's metres between his
    # body and his edge of the frame); the rest of the step is toward us. A recoil past the edge is a body cut by it.
    # With no room beside him he steps BACK from the lens and out: DEEP further off the frame is wider by DEEP times
    # its half-width over his distance, and that is the room he steps into. The reaction brings him back to where he
    # worked. Both moves cross the sheet: KEYS measures his travel ON SCREEN, and a step along the lens alone is none.
    room = float(st.get("room", 0.1)); tight = not planted and room - 0.02 < ROOMY
    # WHERE HE DUCKS BACK TO. On screen a step out to his side and a step back from the lens CANCEL (further off he is
    # smaller, and smaller is nearer the middle): the two together measured 0.050 of the frame where either alone is
    # more. So it is one or the other: sideways where the frame has the room, else straight back along the lens.
    if planted:                                       # on a step his feet stay on it: his weight goes to his own side and back
        back = S2 + cross * max(0.0, min(0.05, room - 0.03)); end = S2; how = "planted"
    elif not tight:
        lat = min(k_recoil, room - 0.02)
        back = S2 + cross * lat + to_us * (k_recoil - lat)
        end = back - cross * lat + to_us * TO_LENS[1]; how = "roomy"          # back in from the edge and to us: a new place on the sheet
    elif room - 0.02 >= SIDE_MIN:
        back = S2 + cross * (room - 0.02); end = S2; how = "a step to his side"
    else:
        back = S2 - to_us * DEEP; end = S2; how = "no room beside him: straight back"
    lean_back = -6.0 if tight else ks[2]["spine"]     # leaning back is leaning to his own edge of the frame: less of it where there is no room
    yaw_res = yaw_act if (fn or tool) else ks[2]["yaw"]       # at the result his chest is still to the job; the turn to us is the reaction
    sway = SWAY * (0.5 if planted else 1.0); squat = BRACE * 1.5                                  # his knees do what his feet cannot (2.2 over-bent them)
    tang = Vector((-away.y, away.x, 0.0)); tang = tang if tang.dot(lens) > 0 else -tang           # his weight shifts ROUND the job, not off it: the hand stays in reach
    sway_v = (tang if (fn or tool) else lens) * sway
    # THE CHEER: from the reaction to the cut and past it his arms go up, down, up and his knees with them, so no pose
    # is held (motion.py HOLD: 0.8 s) and still 4 lands on "up". The poses are 14 cm or more apart at the hand; "up",
    # "guard", "show" and "high" were all within 7 cm of each other, which HOLD read as one held pose.
    beats = [("up" if k % 2 == 0 else "drop", R_ + CHEER * k) for k in range(0, 40) if R_ + CHEER * k <= dur + TAIL + CHEER]
    # THREE HEIGHTS, one per still after the first: he works crouched, comes up tall as he lets go and ducks back, and
    # lands the reaction with his knees bent and his arms up. He comes in from a little further off (where the frame is
    # wider), is turned to the job before his hand goes to it, and bends to it only as the hand arrives.
    start = D + away * max(0.0, min(k_walk, room - 0.03)) - to_us * (0.0 if planted else WALK_DEEP)
    sp1 = ks[1]["spine"]
    pre = [(0.0, start, 0.0, ks[0]["yaw"], -6.0),                 # upright, a touch back on his heels: the lean INTO the job is a move the sheet sees
           (max(0.2, T["action"] - ARRIVE), start + (S - start) * 0.5, 0.0, yaw_act, -2.0),
           (max(0.25, T["action"] - BEND), start + (S - start) * 0.85, 0.0, yaw_act, 1.0)]
    if tv is not None:                                # a push: his walk keys the frames between
        work = [(T["action"], S, 0.0, yaw_act, sp1), (T["release"], S2, 0.0, math.degrees(math.atan2(tv.x, -tv.y)), sp1)]
    elif pick:        # his hand is on a thing that stays put until he has it: he is still at it, then comes up WITH it
        work = [(T["action"], S, -BRACE * 1.4, yaw_act, sp1), (T["action"] + PICK_S, S, -BRACE * 1.4, yaw_act, sp1),
                (T["release"], S + to_us * (0.0 if tight else 0.04), 0.0, yaw_act, sp1)]
    else:
        work = [(T["action"], S, -BRACE, yaw_act, sp1), ((T["action"] + T["release"]) / 2, S + sway_v, -BRACE * 1.7, yaw_act, sp1 + 5.0),
                (T["release"], S, 0.0, yaw_act, sp1)]
    post = [(T["result"], back - GR, 0.0, yaw_res, lean_back), (T["result"] + PAUSE, back - GR, 0.0, yaw_res, lean_back)]
    post += [(t_, end - GR + to_us * (0.0 if planted or tight else min(0.06, 0.015 * i)), -squat if name == "up" else -0.01, ks[3]["yaw"], 8.0 if name == "up" else 2.0)
             for i, (name, t_) in enumerate(beats)]
    knots = pre + work + post

    print(f"STAGE perform: he comes in from ({start.x:.2f}, {start.y:.2f}), works at ({S.x:.2f}, {S.y:.2f}), lets go at ({S2.x:.2f}, {S2.y:.2f}), ducks back to "
          f"({back.x:.2f}, {back.y:.2f}), ends at ({end.x:.2f}, {end.y:.2f}); frame room beside him {room:.2f} m ({how}); "
          f"action {T['action']:.2f}s release {T['release']:.2f}s result {T['result']:.2f}s reaction {T['reaction']:.2f}s", flush=True)

    def at(t):
        for (ta, pa, za, ya, sa), (tb, pb, zb, yb, sb) in zip(knots, knots[1:]):
            if t <= tb:
                u = sm(max(0.0, min(1.0, (t - ta) / max(1e-6, tb - ta))))
                return pa + (pb - pa) * u + (G(t) if tv is None else Vector((0, 0, 0))), za + (zb - za) * u, ya + ((yb - ya + 180.0) % 360.0 - 180.0) * u
        return knots[-1][1] + (GR if tv is None else Vector((0, 0, 0))), knots[-1][2], knots[-1][3]

    nf = int(round((dur + TAIL) * fps)) + 1
    fa, fr = int(round(T["action"] * fps)) + 1, int(round(T["release"] * fps)) + 1
    for f in range(1, nf + 1):
        if tv is not None and fa < f <= fr:
            continue                                 # his walk keys these
        t = (f - 1) / fps; p, dz, yaw = at(t)
        data._kobj(t, loc=(p.x, p.y, z0 + dz), rot=math.radians(yaw))
        data._plant_feet_here(t, lift=(z0, z0))
        if tv is not None and f == fa:               # he walks with it: stepped feet, a lean into it (character.walk_to)
            data.walk_to((S2.x, S2.y), T["action"], T["release"], pushing=True, lean=8.0)
    if tv is not None:
        def moved(t, _c={}):
            f_ = max(fa, min(fr, int(round(t * fps)) + 1))
            if f_ not in _c:
                data.sc.frame_set(f_); _c[f_] = Vector((data.arm.location.x - S.x, data.arm.location.y - S.y, 0.0))
            return _c[f_].copy()
        T["moved"] = moved
    for t, _p, _z, _y, sp in knots:
        data._k("spine", t, rot=(sp, 0, 0))
    data.look_at(grab, 0.0, max_yaw=min(ks[0]["head"], 8.0) if (fn or tool) else ks[0]["head"], max_pitch=25, blend=0.0)      # his chest turns to the job as he comes in: his head adds little, or still 1 is a profile        # his head turns to the prop only as far as his face stays to us
    if fn or tool:                                    # his chest is round to the job by the time he is at it: his head adds little, or his face is past FACE_LIMIT on still 1
        data.look_at(g0, max(0.2, T["action"] - ARRIVE), max_yaw=4.0, max_pitch=25, blend=0.2)
    data.look_at(g0, T["action"], max_yaw=min(12.0, ks[1]["head"]) if not (fn or tool) else 4.0, max_pitch=25, blend=0.2)
    if tv is not None:                               # across the frame his body is side-on: his HEAD is turned to us the whole walk
        data.look_at(cam, T["action"] + 0.05, max_yaw=PUSH_HEAD, max_pitch=25, blend=0.2)
        data.look_at(cam, T["release"], max_yaw=PUSH_HEAD, max_pitch=25, blend=0.2)
    data.look_at(g0 + (tv if tv is not None else gd(T["release"])), T["result"], max_yaw=ks[2]["head"], max_pitch=25, blend=0.2)
    data.look_at(cam, T["reaction"] - 0.15, max_yaw=55, max_pitch=40, blend=0.3)
    if faces:
        data.expression(faces[0], T["action"], T["reaction"] - 0.3, blend=0.12)
        data.expression(faces[1], T["reaction"] - 0.25, dur + 1.0, blend=0.25)
    pose_at = (("ready", 0.0), ("work", T["action"]), ("up", T["release"]), ("drop", T["result"]), ("drop", T["result"] + PAUSE)) + tuple(beats)      # his free hand flies up as he lets go, both drop as he ducks back
    mid = (T["action"] + T["release"]) / 2             # the hand with a tool in it WORKS it: down, a prod, back, then up to show it
    keeps = (("ready", 0.0), ("work", T["action"]), ("prod", mid), ("work", T["release"]), ("prod", T["result"]), ("prod", T["result"] + PAUSE)) \
        + tuple(("high" if name == "up" else "work", t_) for name, t_ in beats)
    for sd in "LR":
        sg = -1 if sd == "L" else 1
        for name, t in (keeps if sd == side and (pick or tool) else pose_at):
            if sd == side and not tool and (pick or t < R_ - 1e-6):
                continue                                                          # this hand has the job: reach() carries it there (and back)
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), ARMS[name](sg)):
                data._k(bn, t, rot=r)
    T["pick"] = 0.0 if tool else None
    if side and fn and pick:
        T["pick"] = T["action"] + PICK_S                                          # his hand is ON it this long before it leaves its place
        # then the HAND carries it, on a line, up in front of his own shoulder and higher at the reaction; the thing rides
        # in it (carry()). Every frame an IK solve to a point that goes with his body: no joint angle is ever keyed.
        rest = Vector(fn(T["action"]))

        def held_at(t):                  # reach() has the scene ON this frame: the show point hangs off his shoulder as it is now
            if t <= T["pick"]: return rest
            p_, _dz, yw = at(t); sh = data._shoulder_w(side); yr = math.radians(yw)
            fwd = Vector((math.sin(yr), -math.cos(yr), 0.0)); out = Vector((sh.x - p_.x, sh.y - p_.y, 0.0)); out -= fwd * out.dot(fwd)
            out = out.normalized() if out.length > 1e-6 else Vector((0, 0, 0))
            rise = SHOW_RISE * sm(max(0.0, min(1.0, (t - T["result"] - PAUSE) / max(1e-6, R_ - T["result"] - PAUSE))))
            show = sh + fwd * SHOW_OUT + out * SHOW_SIDE + Vector((0, 0, SHOW_UP + rise))
            return rest.lerp(show, sm(max(0.0, min(1.0, (t - T["pick"]) / (T["release"] + 0.2 - T["pick"])))))     # up by the time he steps back
        data.reach(side, held_at, T["action"], dur + TAIL, lead=LEAD, back=None)
    elif side and fn:
        data.reach(side, fn, T["action"], T["release"], lead=LEAD, back=0.6)
    T["hand"] = side
    return T


def carry(data, objs, T):
    """the things in his hand ride in it from T["pick"] to the end (a Child Of on his hand bone, switched on at that
    frame with the offset they have there, so nothing jumps). Call AFTER data.finish(): the hand's pose is final then."""
    import bpy
    side = T.get("hand"); t = T.get("pick")
    if side is None or t is None:
        raise SystemExit("recipe_stage.carry: perform() put nothing in his hand (pick=True with a grip in reach, or tool=True)")
    fps = __import__("clock").FPS; f = int(round(t * fps)) + 1
    data.sc.frame_set(f); bpy.context.view_layer.update()
    bone = data.pb[f"hand.{side}"]
    for o in objs:
        c = o.constraints.new("CHILD_OF"); c.name = "in his hand"; c.target = data.arm; c.subtarget = bone.name
        c.inverse_matrix = (data.arm.matrix_world @ bone.matrix).inverted()
        if f > 1:
            c.influence = 0.0; c.keyframe_insert("influence", frame=f - 1)
        c.influence = 1.0; c.keyframe_insert("influence", frame=f)
        for fc in (__import__("character")._fcurves(o.animation_data.action) if o.animation_data and o.animation_data.action else []):
            if fc.data_path.endswith("influence"):
                for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
    return objs


def frame(data, st, dur=None, t=None, fstop=11.0):
    """build the shot's camera. With the beat's length `dur` (or a time t) the staging's camera is solved again on his
    REAL body as he stands at the action (compose.frame_data); with neither, the staging's own camera is built."""
    import scene_kit as K
    if dur is None and t is None:
        return K.camera(tuple(st["cam"]), tuple(st["look"]), lens=st["lens"], fstop=fstop)
    at = t if t is not None else st["times"]["action"] * dur
    cam_loc, look = compose.frame_data(data, st["cam"], st["look"], st["lens"], face_at=st["face_at"], height=st["frame_h"], t=at)
    return K.camera(tuple(cam_loc), tuple(look), lens=st["lens"], fstop=fstop)


# ------------------------------------------------------------------ a planned story's first shots file

STUB_HEAD = '''"""{story}: the shots, staged from stories/{story}/plan.json by store/recipe_stage.py.
Build each prop and its set from their real parts; the staging, the four poses and the camera come from the recipe."""
import recipe_stage, shot_plan
'''

STUB_SHOT = '''

def shot{n}():
    """{line}
    ACTION: {action}
    CONSEQUENCE: {consequence}
    STILLS: {stills}"""
    plan = shot_plan.shot(STORY, {n})
    P = place_{place}()                      # TODO build the set; it returns dict(light=..., prop=<the '{prop}' root>, size=(across, deep, tall))
    st = recipe_stage.from_plan(plan, prop_at=tuple(P["prop"].location), prop_size=P["size"])
    if not st["ok"]: raise SystemExit("shot {n}: " + st["why"])
    data = load_data(); recipe_stage.place(data, st)
    T = recipe_stage.perform(data, st, DUR)  # TODO grip=lambda t: <the point his hands are on> when the plan puts his hands on a prop
    # TODO the prop's own animation: at T["action"] {action}; by T["result"] {consequence}
    data.finish(); recipe_stage.frame(data, st, DUR)
    return dict(lanes=[], kiosks=[], place="{place}", light=P["light"], data=data, rest=1, grips=({grips}), cutaway=None, boxes=[],
                conseq=[("{consequence}", lambda: meshes([P["prop"]]), T["action"], DUR, {{"moves": True}})])
'''


def stub(story):
    """the text of a first shots.py for a planned story: one short function a shot, each a call into the recipe"""
    import json
    import shot_plan
    script = json.loads((shot_plan.STORIES / story / "script.json").read_text())
    plan = shot_plan.load(story)
    bad = [f"{w}: {t}" for w, t in shot_plan.problems(story, script)] if plan is not None else [f"no stories/{story}/{shot_plan.NAME}"]
    if bad:                                          # no shots file is started around the plan
        raise SystemExit(f"{story}: no stub without a plan that passes (python tools/data3d/store/shot_plan.py check {story}):\n  " + "\n  ".join(bad))
    out = [STUB_HEAD.format(story=story)]
    sets = script.get("sets") or []
    for n, p in enumerate(plan["shots"], 1):
        p = p or {}
        held = sorted({s.get("hands") for s in p.get("stills") or [] if s.get("hands") not in (None, "free")})
        out.append(STUB_SHOT.format(n=n, line=(script.get("lines") or [""] * n)[n - 1], action=p.get("action", ""), consequence=p.get("consequence", ""),
                                    stills=" | ".join(str(s.get("shows", "")) for s in p.get("stills") or []), prop=p.get("prop", ""),
                                    place=sets[n - 1] if n <= len(sets) else f"set{n}", grips="".join(f'"{h}", ' for h in held)))
    out.append("\n\nSHOTS = {" + ", ".join(f"{n}: shot{n}" for n in range(1, len(plan["shots"]) + 1)) + "}\n")
    return "".join(out)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "stub":
        print(stub(sys.argv[2])); sys.exit(0)
    print("usage: recipe_stage.py stub STORY"); sys.exit(1)
