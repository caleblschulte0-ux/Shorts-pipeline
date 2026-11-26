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
                                   "reach": True when the prop is also inside his reach (NEAR, WORK_DEG: props up to
                                   about 0.6 m); a taller prop is framed with him nearer the lens, out of reach, and
                                   perform() then keys no hand on it and says so.
  from_plan(plan_shot, prop_at, prop_size)   the same, read off the shot's plan (store/shot_plan.py)
  place / perform / frame          in Blender, on his rig: stand him there, key the four poses, solve the real camera
                                   on his real body (compose.frame_data) and build it
  stub(story)                      a shots file for a planned story, a few lines a shot, calling these

WHAT perform() WAS MEASURED ON, and what it was not. One scratch shot (a 0.5 m crate on locations.field(), his hand on
it while it moved 0.1 m, 4.6 s) built through store/shots.py with no render: STAGING, KEYS, TALKING, CAUSE, ANATOMY,
CLIPPING, TWITCH, FLUID, REACH, POP, HOLD, READ, FAR and RECIPE all read OK. Each of these broke on the way there and is
why a number below is what it is: a key between two frames (36 deg/frame arm snap), a walk of over 0.25 m on planted
feet (GLIDE), a hand job from too far (REACH) or from inside the prop (CLIPPING), nothing moving while he works (READ),
a reaction that only steps toward the lens (KEYS: stills 3 and 4 one picture). It is NOT proven for every prop: the same
crate 0.62 m tall and pushed straight away from the lens put his arm behind his back (ANATOMY) and his head 2 cm into
it (CLIPPING), after which NEAR's floor went from 0.14 to 0.2 and was not re-run. So perform() is a first performance
that the store's own checks still judge on every build, never a pass they can skip; and the prop's own animation (how
far it moves, whether it stays in frame and big) is the shot's, checked by CONSEQUENCE and RECIPE EDGE as before.

A new story's shot is then:

    def shot3():
        P = place_my_set()                                   # the set and the prop, built from their real parts
        plan = shot_plan.shot(STORY, 3)
        st = recipe_stage.from_plan(plan, prop_at=P["prop"].location, prop_size=(0.5, 0.4, 0.6))
        data = load_data(); recipe_stage.place(data, st)
        recipe_stage.perform(data, st, DUR, grip=lambda t: handle_point(t))     # his hands ON the prop through the action
        ...the prop's own animation: what the action does to it, keyed at st["times"]...
        data.finish(); cam = recipe_stage.frame(data, st)
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
THREE_Q = (35.0, 28.0, 42.0, 50.0)           # degrees his chest is turned off the lens toward the prop
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
PAUSE = 0.25                           # seconds he holds the recoil before he turns to us
STAND_OFF = (0.3, 0.27, 0.24, 0.21, 0.18)   # metres he stands back from the grip: the furthest his shoulder still reaches from
PALM = 0.02                            # metres his palm sits proud of the face it is on
REACH_D = 0.18                         # metres, shoulder to the job (character.reach: about 0.18 is the arm's length)
WALK_IN = 0.05                         # metres he starts further off and walks in
BRACE = 0.06                           # metres his knees bend as he works (lava shot 3: 0.07), and again as he lands the reaction
SWAY = 0.08                            # metres his weight shifts to us and back as he works, so the work reads (motion.py READ)
HOLD_MOVE = 0.12                       # metres the grip may travel in his hand: he stands and works, a longer push is acts.push
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


def stage(prop_at, prop_size, side="left", stands="beside", frame_h=None, view_az=0.0, whole=True, focus=None, cam_h=0.5, lens=LENS):
    """_stage() with the prop inside his reach when the frame allows it ("reach": True: perform() can put his hand on
    it), else the same recipe with the prop beside him out of reach ("reach": False: a prop taller than about a metre
    is framed with him nearer the lens than it; he works it with a tool, a throw or a walk the shot keys itself)"""
    st = _stage(prop_at, prop_size, side, stands, frame_h, view_az, whole, focus, cam_h, lens, reach=True)
    if not st["ok"]:
        st = _stage(prop_at, prop_size, side, stands, frame_h, view_az, whole, focus, cam_h, lens, reach=False)
    return st


def _stage(prop_at, prop_size, side="left", stands="beside", frame_h=None, view_az=0.0, whole=True, focus=None, cam_h=0.5, lens=LENS, reach=True):
    """where he stands, his yaw, the camera and the four keys for a prop at prop_at (x, y, its foot's z) of prop_size
    (across, deep, tall; metres). side: which side of the frame HE is on. view_az: the way the lens looks, degrees
    round from +Y (0 looks along +Y, 90 along +X). whole=False: the thing runs past the frame by design; `focus` (a
    world point, default the prop's near foot) is where the event happens and sits mid-frame. Returns a dict; "ok"
    False and "why" when no staging fits (the prop is too big to be whole beside him: come closer to less of it)."""
    px, py, pz = (float(v) for v in prop_at); w, d, h = (float(v) for v in prop_size)
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
            for lat in sorted({round(max(0.45, 0.5 * fwd), 3), round(max(base, 0.5 * fwd), 3), round(half_across + 0.2, 3), round(half_across + 0.26, 3), round(max(base, 0.5 * fwd) + 0.2, 3), round(max(base, 0.5 * fwd) + 0.5, 3)}):
                for fx in FACE_X:
                    for tq in THREE_Q:
                        tried += 1
                        D = (ex + R[0] * s * lat + C[0] * fwd, ey + R[1] * s * lat + C[1] * fwd, pz)
                        tr = math.radians(tq)
                        f = _unit((C[0] * math.cos(tr) - s * R[0] * math.sin(tr), C[1] * math.cos(tr) - s * R[1] * math.sin(tr)))
                        face = (D[0], D[1], D[2] + FACE_Z); crown = (D[0], D[1], D[2] + DATA_H); foot = D
                        cam0 = (D[0] + C[0] * 2.0, D[1] + C[1] * 2.0, D[2] + cam_h)
                        look0 = (cam0[0] + v[0], cam0[1] + v[1], cam0[2])
                        face_at = (fx if side == "left" else 1 - fx, FACE_Y)
                        cl, lk, rep = compose.solve_camera(face, crown, foot, cam0, look0, lens, face_at, hgt)
                        if not rep["ok"]:
                            why = "the camera solve did not converge"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        pin = compose.Pinhole(cl, lk, lens)
                        to_cam = _unit((cl[0] - D[0], cl[1] - D[1]))
                        chest = _angle(f, to_cam)
                        near = (min(max(D[0], px - w / 2), px + w / 2) - D[0], min(max(D[1], py - d / 2), py + d / 2) - D[1]) if whole else (ex - D[0], ey - D[1])
                        bearing = _angle(f, _unit(near)) if math.hypot(*near) > 0.05 else 0.0
                        if not SQUARE_DEG < chest <= CHEST_MAX:
                            why = f"his chest would be {chest:.0f} degrees off the lens"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        if reach and whole and (not NEAR[0] <= math.hypot(*near) <= NEAR[1] or bearing > WORK_DEG):
                            why = (f"his hands would not reach the prop from where he stands ({math.hypot(*near):.2f} m off its face, {bearing:.0f} degrees round "
                                   f"from his chest; {NEAR[0]} to {NEAR[1]} m and {WORK_DEG:.0f} degrees at most)"); whys[why.split("(")[0][:60]] = (whys.get(why.split("(")[0][:60], (0, why))[0] + 1, why); continue
                        if bearing >= BEHIND_DEG:
                            why = "the prop would be behind his back"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        him = [pin.project((D[0] + R[0] * a, D[1] + R[1] * a, D[2] + z)) for a in (-HALF_W, HALF_W) for z in (0.0, DATA_H)]
                        if any(not (PAD <= q[0] <= 1 - PAD and 0.0 <= q[1] <= 1.0) for q in him):
                            why = "he would be cut by the frame edge"; whys[why.split(":")[0][:60]] = (whys.get(why.split(":")[0][:60], (0, why))[0] + 1, why); continue
                        b, front = compose.bbox(pin.project, prop_pts)
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
                        away = _unit((D[0] - ex, D[1] - ey)) if not whole or math.hypot(*near) < 0.05 else _unit((-near[0], -near[1]))
                        gx, gy = ((D[0] + near[0] + away[0] * PALM, D[1] + near[1] + away[1] * PALM) if whole else (ex, ey))     # on its face nearest him
                        grab = (gx, gy,
                                (focus[2] if focus is not None and len(focus) > 2 else pz + min(0.7 * h, 0.36)))
                        chests = (chest, min(chest + 12.0, CHEST_MAX + 5.0), max(SQUARE_DEG + 2.0, chest - 6.0), SQUARE_DEG + 2.0)
                        steps = ((0.0, 0.0), (-away[0] * 0.05, -away[1] * 0.05), (away[0] * 0.1, away[1] * 0.1), (away[0] * 0.1, away[1] * 0.1))
                        keys = [{"event": e, "at": KEYS_AT[i], "yaw": yaw if i == 0 else _toward(yaw, yaw_at(chests[i]), 1.0), "chest": chests[i], "step": steps[i],
                                 "looks": "lens" if e == "reaction" else "prop", "head": 3.0 if e == "reaction" else max(4.0, min(FACE_TURN, FACE_LIMIT - chests[i])),
                                 "arms": ARM_OF[e], "spine": SPINE_OF[e]} for i, e in enumerate(EVENTS)]
                        return {"ok": True, "why": "", "side": side, "stands": stands, "data_at": D, "yaw": yaw, "cam": cl, "look": lk, "lens": lens,
                                "face_at": face_at, "frame_h": hgt, "chest_deg": chest, "bearing": bearing, "prop_box": b, "prop_at": (px, py, pz),
                                "prop_size": (w, d, h), "grab": grab, "keys": keys, "times": dict(TIMES), "tried": tried, "whole": whole, "reach": bool(reach and whole)}
    if whys:                                     # the reason most of the candidates fell to, not the last one tried
        why = max(whys.values())[1]
    return {"ok": False, "why": why, "tried": tried, "side": side, "stands": stands}


def _toward(a, b, k):
    """yaw a turned a share k of the way to yaw b, the short way round (degrees)"""
    d = (b - a + 180.0) % 360.0 - 180.0
    return a + d * k


def from_plan(plan_shot, prop_at, prop_size, view_az=0.0, focus=None, cam_h=0.5):
    """stage() read off a shot's plan (store/shot_plan.py): his side, where he stands, his size, whether the prop is whole"""
    d = plan_shot.get("data") or {}
    prop = next((p for p in plan_shot.get("props") or [] if p.get("name") == plan_shot.get("prop")), {})
    st = stage(prop_at, prop_size, side=d.get("side", "left"), stands=d.get("stands", "beside"), frame_h=None, view_az=view_az,
               whole=bool(prop.get("whole", True)), focus=focus, cam_h=cam_h)
    if st["ok"] and isinstance(d.get("frame_h"), (int, float)) and d["frame_h"] >= MIN_H:
        want = stage(prop_at, prop_size, side=d.get("side", "left"), stands=d.get("stands", "beside"), frame_h=float(d["frame_h"]),
                     view_az=view_az, whole=bool(prop.get("whole", True)), focus=focus, cam_h=cam_h)
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
}


def place(data, st):
    """stand him where the staging says, feet on the prop's ground"""
    x, y, z = st["data_at"]
    data.place(x, y, st["yaw"]); data.arm.location.z = z
    return data


def perform(data, st, dur, grip=None, faces=("alarmed", "pleased"), ground_z=None):
    """key the four events on his whole body, one move running into the next so no stretch of the beat is a held pose:
    he walks in looking at the prop (before); at the action he is at the prop with his near hand ON grip(t) (a callable
    t -> world point, or a point; he walks with it while it moves) and leans through it; at the result he lets go and
    recoils a step; at the reaction he turns to the lens, steps to us and throws both arms up. Feet planted on every
    frame. Returns the times {before, action, release, result, reaction}. Call before data.finish()."""
    from mathutils import Vector
    import acts
    fps = getattr(acts, "FPS", None) or __import__("clock").FPS
    T = {k: round(v * dur * fps) / fps for k, v in st["times"].items()}      # on a frame: a key between two frames bends both
    T["reaction"] = max(T["reaction"], T["release"] + 0.9); T["end"] = dur
    x0, y0, z0 = st["data_at"]; z0 = z0 if ground_z is None else ground_z
    ks = st["keys"]
    grab = Vector(st["grab"]); cam = Vector(st["cam"])
    fn = None if grip is None else (grip if callable(grip) else (lambda t, p=Vector(grip): p))
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

    side = None; off = min(STAND_OFF[0], (D - Vector((g0.x, g0.y, 0.0))).length)
    if fn:                                            # the hand whose shoulder is nearer does the job, from as far back as it reaches
        for off in STAND_OFF:
            S = stand(off)
            data._kobj(T["action"], loc=(S.x, S.y, z0), rot=math.radians(ks[1]["yaw"])); data.sc.frame_set(int(round(T["action"] * fps)) + 1)
            d = {sd: ((data.arm.matrix_world @ data.pb[f"arm.{sd}"].head) - g0).length for sd in "LR"}
            side = min(d, key=d.get)
            if d[side] <= REACH_D: break
    S = stand(off) if fn else D + (Vector((g0.x, g0.y, 0.0)) - D).normalized() * min(0.08, (Vector((g0.x, g0.y, 0.0)) - D).length * 0.3)
    gd = lambda t: (Vector(fn(min(t, T["release"]))) - g0) if fn else Vector((0, 0, 0))
    if gd(T["release"]).length > HOLD_MOVE:
        print(f"STAGE: the grip travels {gd(T['release']).length:.2f} m in his hand (perform() stands and works: {HOLD_MOVE} m at most; "
              f"a longer push is acts.push or walk_to)", flush=True)
    back = S + (away + lens * 0.4).normalized() * RECOIL
    cross = Vector((-lens.y, lens.x, 0.0)); cross = cross if cross.dot(away) > 0 else -cross      # across the screen, to his own side
    end = back - cross * TO_LENS[0] + lens * TO_LENS[1]                      # back to the middle and to us: a new place on the sheet
    knots = [(0.0, D + away * WALK_IN, 0.0, ks[0]["yaw"], ks[0]["spine"]), (T["action"], S, -BRACE, ks[1]["yaw"], ks[1]["spine"]),
             ((T["action"] + T["release"]) / 2, S + lens * SWAY, -BRACE * 1.7, ks[1]["yaw"], ks[1]["spine"] + 5.0),
             (T["release"], S, -BRACE * 0.4, ks[1]["yaw"], ks[1]["spine"]), (T["result"], back, 0.0, ks[2]["yaw"], ks[2]["spine"]),
             (T["result"] + PAUSE, back, 0.0, ks[2]["yaw"], ks[2]["spine"]), (T["reaction"], end, -BRACE, ks[3]["yaw"], 8.0),
             (dur, end + lens * 0.04, 0.0, ks[3]["yaw"], ks[3]["spine"])]
    sm = lambda u: u * u * (3 - 2 * u)

    def at(t):
        for (ta, pa, za, ya, sa), (tb, pb, zb, yb, sb) in zip(knots, knots[1:]):
            if t <= tb:
                u = sm(max(0.0, min(1.0, (t - ta) / max(1e-6, tb - ta))))
                return pa + (pb - pa) * u, za + (zb - za) * u, ya + ((yb - ya + 180.0) % 360.0 - 180.0) * u
        return knots[-1][1], knots[-1][2], knots[-1][3]

    nf = int(round(dur * fps)) + 1
    for f in range(1, nf + 1):
        t = (f - 1) / fps; p, dz, yaw = at(t)
        data._kobj(t, loc=(p.x, p.y, z0 + dz), rot=math.radians(yaw))
        data._plant_feet_here(t, lift=(z0, z0))
    for t, _p, _z, _y, sp in knots:
        data._k("spine", t, rot=(sp, 0, 0))
    data.look_at(grab, 0.0, max_yaw=ks[0]["head"], max_pitch=25, blend=0.0)        # his head turns to the prop only as far as his face stays to us
    data.look_at(g0, T["action"], max_yaw=min(12.0, ks[1]["head"]), max_pitch=25, blend=0.2)
    data.look_at(g0 + gd(T["release"]), T["result"], max_yaw=ks[2]["head"], max_pitch=25, blend=0.2)
    data.look_at(cam, T["reaction"] - 0.15, max_yaw=55, max_pitch=40, blend=0.3)
    if faces:
        data.expression(faces[0], T["action"], T["reaction"] - 0.3, blend=0.12)
        data.expression(faces[1], T["reaction"] - 0.25, dur + 1.0, blend=0.25)
    pose_at = (("ready", 0.0), ("work", T["action"]), ("whoa", T["result"]), ("up", dur * 0.96), ("up", dur + 0.5))
    for sd in "LR":
        sg = -1 if sd == "L" else 1
        for name, t in pose_at:
            if sd == side and t < dur * 0.9:
                continue                                                          # this hand has the job: reach() carries it there and back
            for bn, r in zip((f"arm.{sd}", f"fore.{sd}", f"hand.{sd}"), ARMS[name](sg)):
                data._k(bn, t, rot=r)
    if side:
        data.reach(side, fn, T["action"], T["release"], lead=0.7, back=0.6)
    T["hand"] = side
    return T


def frame(data, st, t=None, fstop=11.0):
    """solve the real camera on his real body at the action (compose.frame_data) from the staging's lens, and build it"""
    import scene_kit as K
    dur_t = st["times"]["action"] if t is None else t
    cam_loc, look = compose.frame_data(data, st["cam"], st["look"], st["lens"], face_at=st["face_at"], height=st["frame_h"], t=dur_t)
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
    data.finish(); recipe_stage.frame(data, st)
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
