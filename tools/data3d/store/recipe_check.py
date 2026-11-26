"""THE RECIPE, MEASURED: the four board stills of a shot are read off the SCENE before a frame renders, and held to the
staging that passes the board (2026-11-26).

Every 3D short has gone 4 to 18 judge rounds a shot. Tallied over the round reports of lava, cardrewards, helium and
honey (1,225 hard lines, counted by keyword), the same few faults come back in every video: a thing cut by the frame edge (188), a toy or
flat prop (194), a subject too small or the shot too wide (128), a thing floating or with no support (85), a thing
that appears, vanishes or changes place (50), a hand not on what it holds (60), the event behind him (50), one picture
repeated (38). Each was caught by the panel, forty minutes a round, and most of them are geometry: they can be read
off the scene in a second. store/staging.py already measures some of it over the whole shot (his size on most frames,
words cut by the edge, his pose changing between stills); nothing measured the four stills themselves as the judge
sees them, against what the shot said it would show.

  collect(data, cam, nf, S, plan)   in Blender: the FACTS of the four key stills (staging.KEYS_AT), plain numbers: the
                                    lens, his size, his face and chest to the lens, his pose bone by bone, his hands,
                                    and every DECLARED thing (each grip, each consequence, each prop of the shot's
                                    plan) as a group: is it drawn, its box on screen, where it is in the world, how
                                    far it is from his hands, where it lies round him.
  problems(facts, plan)             no Blender: what in those facts breaks the recipe, one sentence each.
  check(...)                        both, printed as RECIPE lines; store/shots.py runs it strict and writes the facts
                                    beside the stills (recipe.json).

The rules (each only ever ADDS a block; none can pass a shot, and the judge's bar is not touched):
  CLOSE    he stands CLOSE_H of the frame or more on at least CLOSE_STILLS of the four stills.
  FACE     on no still is his face further than FACE_MAX from the lens; he is not square-on with the event behind his
           back (BEHIND_DEG round from his chest) on most of the stills.
  FRAME    on every still that is on him, his whole body is inside the frame.
  EVENTS   each still differs from the one before IN KIND: his pose changes bone by bone (POSE_KIND, measured in his
           own frame, so walking nearer or the lens pushing in is not a new pose) or a declared thing changes state in
           the world (moves, grows, comes, goes). And the result is in the WORLD: between the first still and the last
           two, a declared thing has changed. Four stills of one pose, only bigger, fail.
  HANDS    a still whose plan says his hands are on a prop has a hand within REACH of it; a grip that travels between
           two stills has a hand on it at one of them.
  EDGE     no declared thing that is whole (a prop, a grip) is cut by the frame edge on a still it is drawn in.
  CAUSE    no declared whole thing changes place between two stills unless his hand is on it at one of them, a
           consequence declares it moving in that stretch, or the plan's still names the change and its cause.
  PLAN     what the plan's still says is new is measured there (store/shot_plan.py is the plan and its validator).

The numbers are taken from lava shots 3, 4 and 5 as they passed the board (71, 72, 72) and from stagings the board
failed; tests/test_data3d_a_shot_is_born_to_the_recipe.py holds both ends on their recorded facts."""
import json, math, os

KEYS_AT = (0.08, 0.38, 0.68, 0.98)   # store/staging.py KEYS_AT: the board's four stills (store/shots.py KEYS=4)

CLOSE_H = 0.3          # of the frame height, crown to feet. The recipe says a third (the plan and the staging helper hold
                       # 0.33); measured ON the four stills the three lava shots that passed run 0.33 to 0.43
CLOSE_STILLS = 3       # of the four stills (one may be the establishing or the leaving moment)
FACE_MAX = 70.0        # degrees between his face and the lens on a key still: past this he is in profile turning away.
                       # staging.KEY_BACK_DEG calls 100 the back of his head; the board called 80 "three-quarter from
                       # behind" (lava shot 2, 2026-11-26 11:59Z) and the shots that passed never go past 61
OUT_TOL = 0.02         # of the frame: his body (every bone point) may sit this far past a frame edge on a still
SQUARE_DEG = 20.0      # his chest within this of the lens is square-on to it
BEHIND_DEG = 120.0     # a thing this far round from his chest is behind his back
POSE_KIND = 9.0        # degrees: the mean turn of his upper-body bones, in his own frame, that reads as a new pose
STATE_MOVE = 0.12      # metres: a declared thing whose box centre moved this far in the world has changed place
STATE_GROW = 0.15      # of its size: a declared thing whose box grew or shrank this much has changed
REACH = 0.12           # metres from a hand bone's tip to the thing's box: on it (staging.HAND_ON is 0.06 to a part; a
                       # group's box is looser than its parts)
CUT_TOL = 0.004        # of the frame: a box edge may sit this far past the frame edge (compose.TOL)
SEEN_MIN = 0.01        # of the frame height: a thing smaller than this on screen is not drawn for a viewer

UPPER = ("spine", "chest", "neck", "head", "arm.", "fore.", "hand.")
SCALE_ONLY = "one pose scaled"


# ------------------------------------------------------------------ in Blender: the facts

def _is_upper(name):
    return any(name == u or name.startswith(u) for u in UPPER)


def _group_facts(sc, cam, objs, hands, root, chest_fw, w2c, Vector):
    live = [o for o in objs if not o.hide_render and max(abs(v) for v in o.matrix_world.to_scale()) >= 0.01]
    if not live:
        return {"drawn": 0}
    cs = [o.matrix_world @ Vector(c) for o in live for c in o.bound_box]
    lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    q = [w2c(sc, cam, c) for c in cs]
    front = [v for v in q if v.z > 0]
    box = [min(v.x for v in front), min(v.y for v in front), max(v.x for v in front), max(v.y for v in front)] if front else None

    def gap(p):
        best = 9.0
        for o in live:
            oc = [o.matrix_world @ Vector(c) for c in o.bound_box]
            a = Vector((min(c.x for c in oc), min(c.y for c in oc), min(c.z for c in oc)))
            b = Vector((max(c.x for c in oc), max(c.y for c in oc), max(c.z for c in oc)))
            n = Vector((min(max(p.x, a.x), b.x), min(max(p.y, a.y), b.y), min(max(p.z, a.z), b.z)))
            best = min(best, (p - n).length)
        return best

    near = Vector((min(max(root.x, lo.x), hi.x), min(max(root.y, lo.y), hi.y), 0.0)) - Vector((root.x, root.y, 0.0))
    bearing = None
    if near.length > 0.05 and chest_fw.length > 1e-4:
        bearing = round(math.degrees(chest_fw.angle(near)), 1)
    return {"drawn": len(live), "box": [round(v, 4) for v in box] if box else None, "all_front": len(front) == len(q),
            "centre": [round(v, 3) for v in (lo + hi) / 2], "dims": [round(v, 3) for v in (hi - lo)],
            "hand_gap": round(min(gap(h) for h in hands), 3) if hands else None,
            "away": round(near.length, 3), "bearing": bearing}


def groups_of(S, plan=None):
    """every DECLARED thing of the shot as {key: (label, objects, whole, kind)}: each grip prefix, each consequence,
    each prop of the shot's plan (by its object-name prefixes). Resolved now: a consequence may be a callable"""
    import bpy
    out = {}
    drawn = [o for o in bpy.context.scene.objects if o.type in ("MESH", "FONT", "CURVE")]

    def named(prefixes):
        return [o for o in drawn if any(o.name.startswith(p) or (o.parent and o.parent.name.startswith(p)) for p in prefixes)]

    for g in S.get("grips") or ():
        out[f"grip:{g}"] = (g, named([g]), True, "grip")
    for i, it in enumerate(S.get("conseq") or []):
        label, objs = it[0], it[1]
        opt = it[4] if len(it) > 4 else {}
        objs = objs() if callable(objs) else objs
        objs = [o for o in objs if getattr(o, "type", "") in ("MESH", "FONT", "CURVE")]
        out[f"conseq:{i + 1}"] = (label, objs, bool(opt.get("whole", True)), "conseq")
    for p in (plan or {}).get("props") or []:
        if p.get("objects"):
            out[f"prop:{p['name']}"] = (p["name"], named(list(p["objects"])), bool(p.get("whole", True)), "prop")
    return out


def collect(data, cam, nf, S, plan=None, fps=30):
    """the facts of the four key stills, as plain numbers (JSON)"""
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view as w2c
    sc = bpy.context.scene
    groups = groups_of(S, plan)
    cut = S.get("cutaway")
    stills = []
    for at in KEYS_AT:
        f = max(1, min(nf, int(round(at * (nf - 1))) + 1))
        sc.frame_set(f); bpy.context.view_layer.update()
        m = data.arm.matrix_world; pb = data.pb
        head, top = m @ pb["head"].head, m @ pb["head"].tail
        root = m.translation.copy()
        a, b = w2c(sc, cam, top), w2c(sc, cam, root)
        pts = [w2c(sc, cam, m @ v) for bn in data.arm.pose.bones for v in (bn.head, bn.tail)]
        pts = [p for p in pts if p.z > 0]
        delta = pb["head"].matrix @ pb["head"].bone.matrix_local.inverted()
        fd = (m.to_3x3() @ delta.to_3x3() @ Vector((0, -1, 0))); fd.z = 0
        chest = (m.to_3x3() @ Vector((0, -1, 0))); chest.z = 0
        to_cam = cam.matrix_world.translation - head; to_cam.z = 0
        ang = lambda v: round(math.degrees(v.angle(to_cam)), 1) if v.length > 1e-4 and to_cam.length > 1e-4 else 0.0
        hands = [m @ pb[h].tail for h in ("hand.L", "hand.R") if h in pb]
        pose = {}
        for bn in data.arm.pose.bones:
            d = bn.tail - bn.head
            if d.length > 1e-6:
                d.normalize(); pose[bn.name] = [round(d.x, 4), round(d.y, 4), round(d.z, 4)]
        cm = cam.matrix_world
        stills.append({
            "at": at, "frame": f, "cutaway": bool(cut and cut[0] <= (f - 1) / fps < cut[1]),
            "cam": {"loc": [round(v, 3) for v in cm.translation], "fw": [round(-cm.col[2][i], 4) for i in range(3)], "lens": round(cam.data.lens, 1)},
            "data": {"h": round(abs(a.y - b.y), 4), "face_deg": ang(fd), "chest_deg": ang(chest),
                     "box": [round(min(p.x for p in pts), 4), round(min(p.y for p in pts), 4), round(max(p.x for p in pts), 4), round(max(p.y for p in pts), 4)] if pts else None,
                     "root": [round(v, 3) for v in root], "hands": [[round(v, 3) for v in h] for h in hands], "pose": pose},
            "groups": {k: _group_facts(sc, cam, objs, hands, root, chest, w2c, Vector) for k, (_l, objs, _w, _k) in groups.items()},
        })
    spans = []
    for i, it in enumerate(S.get("conseq") or []):
        opt = it[4] if len(it) > 4 else {}
        spans.append({"key": f"conseq:{i + 1}", "t0": round(float(it[2]), 3), "t1": round(float(it[3]), 3), "moves": bool(opt.get("moves"))})
    return {"nf": nf, "fps": fps, "res": [sc.render.resolution_x, sc.render.resolution_y], "stills": stills, "conseq": spans,
            "groups": {k: {"label": str(l)[:120], "whole": w, "kind": kd, "objects": len(objs)} for k, (l, objs, w, kd) in groups.items()}}


# ------------------------------------------------------------------ no Blender: what the facts break

def pose_turn(p0, p1):
    """the mean angle (degrees) his upper-body bones turned between two stills, in his own frame: walking nearer, the
    lens pushing in or his whole body turning round is not a new pose"""
    angs = []
    for name, a in p0.items():
        b = p1.get(name)
        if b is None or not _is_upper(name):
            continue
        dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
        angs.append(math.degrees(math.acos(dot)))
    return sum(angs) / len(angs) if angs else 0.0


def seen(g):
    """is this group drawn where a viewer can see it: some of its box inside the frame, big enough"""
    b = g.get("box") if g else None
    if not g or not g.get("drawn") or not b:
        return False
    return b[2] > 0 and b[0] < 1 and b[3] > 0 and b[1] < 1 and (min(b[3], 1) - max(b[1], 0)) >= SEEN_MIN


def cut_by_edge(g):
    b = g.get("box")
    if not seen(g):
        return False
    if not g.get("all_front", True):
        return True                                  # part of it is behind the lens: the frame cuts it
    return b[0] < -CUT_TOL or b[1] < -CUT_TOL or b[2] > 1 + CUT_TOL or b[3] > 1 + CUT_TOL


def state_change(g0, g1):
    """how a declared thing changed between two stills, in the world ("" when it did not): comes, goes, moves, grows"""
    s0, s1 = seen(g0), seen(g1)
    d0, d1 = bool(g0 and g0.get("drawn")), bool(g1 and g1.get("drawn"))
    if d0 != d1:
        return "comes" if d1 else "goes"
    if not d0:
        return ""
    if not (s0 or s1):
        return ""                                    # it changed where no viewer sees it
    c0, c1 = g0["centre"], g1["centre"]
    if math.dist(c0, c1) >= STATE_MOVE:
        return "moves"
    z0, z1 = max(g0["dims"]), max(g1["dims"])
    if z0 > 1e-6 and abs(z1 - z0) / z0 >= STATE_GROW:
        return "grows"
    if g0.get("drawn") != g1.get("drawn"):
        return "comes" if g1["drawn"] > g0["drawn"] else "goes"     # some of its parts came or went (crust blocks, steam)
    return ""


def _moving(facts, key, i):
    """does a consequence declare this group moving somewhere between still i and still i+1"""
    t0 = (facts["stills"][i]["frame"] - 1) / facts["fps"]; t1 = (facts["stills"][i + 1]["frame"] - 1) / facts["fps"]
    return any(c["key"] == key and c["t0"] <= t1 and c["t1"] >= t0 for c in facts.get("conseq") or [])


def problems(facts, plan=None):
    """what the four stills break, one sentence each ([] when the staging has the recipe's shape)"""
    st = facts["stills"]; G = facts.get("groups") or {}; out = []
    on = [s for s in st if not s.get("cutaway")]              # a declared cutaway still is not on him
    gap = lambda g: 9.0 if g.get("hand_gap") is None else g["hand_gap"]
    plan_stills = (plan or {}).get("stills") or []
    # ---- CLOSE
    big = [s for s in on if s["data"]["h"] >= CLOSE_H]           # a cutaway still is a wide still: it is the one that may not be close
    need = min(CLOSE_STILLS, len(st))
    if len(big) < need:
        out.append("CLOSE: he stands " + ", ".join(f"{s['data']['h']:.2f}" + (" (cutaway)" if s.get("cutaway") else "") for s in st)
                   + f" of the frame height on the four stills (at least {CLOSE_H} on {need} of them, on him): a wide shot. Come closer to "
                   f"less of the set; the event goes beside him, mid-frame")
    for i, s in enumerate(st, 1):
        b = s["data"].get("box")
        if s.get("cutaway") or not b:
            continue
        if b[0] < -OUT_TOL or b[2] > 1 + OUT_TOL or b[3] > 1 + OUT_TOL or b[1] < -OUT_TOL:
            gone = b[2] <= 0 or b[0] >= 1 or b[3] <= 0 or b[1] >= 1
            out.append(f"FRAME: on still {i} he is {'not in the frame at all' if gone else 'cut by the frame edge'} (his body's box "
                       f"{[round(v, 2) for v in b]}; the frame is 0..1): every still on him shows him whole")
    # ---- FACE
    for i, s in enumerate(st, 1):
        if not s.get("cutaway") and s["data"]["face_deg"] > FACE_MAX:
            out.append(f"FACE: on still {i} his face is {s['data']['face_deg']:.0f} degrees off the lens (at most {FACE_MAX:.0f}): a profile turning "
                       f"away, or the back of his head. Three-quarter to the lens: face and chest to us on every still")
    behind = []
    for i, s in enumerate(st, 1):
        if s.get("cutaway") or s["data"]["chest_deg"] > SQUARE_DEG:
            continue
        ev = [g for k, g in s["groups"].items() if G.get(k, {}).get("kind") in ("conseq", "prop") and seen(g) and g.get("bearing") is not None]
        if ev and all(g["bearing"] >= BEHIND_DEG for g in ev):
            behind.append(i)
    if len(behind) > len(on) / 2:
        out.append(f"FACE: on stills {behind} he stands square to the lens (chest within {SQUARE_DEG:.0f} degrees of it) with every declared "
                   f"thing behind his back: the event is a backdrop. Turn him three-quarter and put it beside him or in front of him")
    # ---- EVENTS
    turns = [pose_turn(st[i]["data"]["pose"], st[i + 1]["data"]["pose"]) for i in range(len(st) - 1)]
    changes = [{k: state_change(st[i]["groups"].get(k), st[i + 1]["groups"].get(k)) for k in G} for i in range(len(st) - 1)]
    for i in range(len(st) - 1):
        world = {k: c for k, c in changes[i].items() if c}
        if turns[i] < POSE_KIND and not world and not (st[i].get("cutaway") != st[i + 1].get("cutaway")):
            grew = st[i + 1]["data"]["h"] / max(1e-6, st[i]["data"]["h"])
            how = f" ({SCALE_ONLY}: he is {grew:.2f} times the size)" if abs(grew - 1) > 0.15 else ""
            out.append(f"EVENTS: stills {i + 1} and {i + 2} are one event{how}: his pose turns {turns[i]:.0f} degrees bone by bone "
                       f"(a new pose is {POSE_KIND:.0f}) and no declared thing changes in the world. Each still is its own moment: "
                       f"before, the action, the result, the reaction")
    if G and len(st) >= 3:
        first = st[0]["groups"]
        res = [k for k in G if any(state_change(first.get(k), s["groups"].get(k)) for s in st[2:])]
        if not res:
            out.append("EVENTS: no declared thing has changed in the world between the first still and the last two: the action has "
                       "no result a viewer can see. The result still shows what the action did, big in the frame")
    elif not G:
        out.append("EVENTS: the shot declares nothing (no consequence, no grip, no prop in its plan): nothing can be measured as its result")
    # ---- HANDS
    for i, s in enumerate(st):
        want = plan_stills[i].get("hands") if i < len(plan_stills) else None
        if want and want != "free":
            g = s["groups"].get(f"prop:{want}") or s["groups"].get(f"grip:{want}")
            if g is None:
                out.append(f"HANDS: the plan puts his hands on '{want}' in still {i + 1} and the shot declares no prop or grip of that name")
            elif not g.get("drawn") or gap(g) > REACH:
                out.append(f"HANDS: the plan puts his hands on '{want}' in still {i + 1}; the nearest hand is "
                           + (f"{g['hand_gap']:.2f} m from it" if g.get("drawn") else "nowhere, it is not drawn") + f" (within {REACH} m)")
    for k, info in G.items():
        if info.get("kind") != "grip":
            continue
        for i in range(len(st) - 1):
            g0, g1 = st[i]["groups"].get(k) or {}, st[i + 1]["groups"].get(k) or {}
            if state_change(g0, g1) != "moves":
                continue
            if min(gap(g0), gap(g1)) > REACH and not _declared(plan_stills, i + 1, info["label"]):
                out.append(f"HANDS: '{info['label']}' is a grip and travels between stills {i + 1} and {i + 2} with no hand within {REACH} m of it "
                           f"on either ({g0.get('hand_gap')} m, {g1.get('hand_gap')} m): it floats beside him")
            g2 = st[i + 2]["groups"].get(k) or {} if i + 2 < len(st) else None
            if g2 is not None and state_change(g1, g2) == "moves" and gap(g1) > REACH:
                out.append(f"HANDS: '{info['label']}' is a grip in mid-move on still {i + 2} (it travels before and after it) and the nearest hand is "
                           f"{g1.get('hand_gap')} m from it (within {REACH} m): a thing he carries has his hands on it")
    # ---- EDGE
    told = set()                                          # one thing named three ways (its grip, its consequence, its plan prop) is said once
    for k, info in G.items():
        if not info.get("whole"):
            continue
        cut = [i + 1 for i, s in enumerate(st) if cut_by_edge(s["groups"].get(k) or {})]
        if cut:
            b = st[cut[0] - 1]["groups"][k]["box"]
            if (tuple(cut), tuple(round(v, 3) for v in b)) in told:
                continue
            told.add((tuple(cut), tuple(round(v, 3) for v in b)))
            out.append(f"EDGE: '{info['label']}' is cut by the frame edge on still(s) {cut} (its box {[round(v, 2) for v in b]}; the frame is 0..1): "
                       f"come closer to less of it or slide it into the frame; a thing that runs past the frame by design is declared whole: False")
    # ---- CAUSE
    for k, info in G.items():
        if not info.get("whole") or info.get("kind") == "grip":
            continue                                     # a grip that travels unheld is HANDS above
        for i in range(len(st) - 1):
            g0, g1 = st[i]["groups"].get(k) or {}, st[i + 1]["groups"].get(k) or {}
            ch = state_change(g0, g1)
            if ch in ("moves", "comes", "goes") and not _moving(facts, k, i) and min(gap(g0), gap(g1)) > REACH \
                    and not _declared(plan_stills, i + 1, info["label"]):
                out.append(f"CAUSE: '{info['label']}' {ch} between stills {i + 1} and {i + 2} and nothing says why: no hand on it, no consequence "
                           f"declares it moving then, and the plan's still names no change to it. A thing that changes place has a cause the stills show")
    for k, info in G.items():
        if info.get("kind") == "prop" and not info.get("objects"):
            out.append(f"PLAN: the plan's prop '{info['label']}' names no object in the scene (its `objects` prefixes match nothing): "
                       f"a prop that is not built cannot be the shot's subject")
    # ---- PLAN
    for i, ps in enumerate(plan_stills[1:len(st)], 1):
        for ch in ps.get("new") or []:
            what, how = ch.get("what"), ch.get("how")
            if what == "data":
                if how == "pose" and turns[i - 1] < POSE_KIND:
                    out.append(f"PLAN: still {i + 1} promises a new pose and his pose turns {turns[i - 1]:.0f} degrees from still {i} (a new pose is {POSE_KIND:.0f})")
                continue
            key = next((k for k in (f"prop:{what}", f"grip:{what}") if k in G), None)
            if key is None:
                out.append(f"PLAN: still {i + 1} promises a change to '{what}' and the shot declares no prop of that name (plan props need `objects`)")
            elif how in MEASURED and not changes[i - 1].get(key) and not any(state_change(st[j]["groups"].get(key), st[i]["groups"].get(key)) for j in range(i)):
                out.append(f"PLAN: still {i + 1} promises '{what}' {how} and it has not changed in the world since any earlier still")
    for i, ps in enumerate(plan_stills[:len(st)]):                # what the plan lists as visible in a still is IN that still
        for e in ps.get("visible") or []:
            name = e if isinstance(e, str) else (e.get("prop") if isinstance(e, dict) else None)
            key = f"prop:{name}"
            if name and name != "data" and key in G and not seen(st[i]["groups"].get(key)):
                out.append(f"PLAN: still {i + 1} lists '{name}' as visible and it is not in the frame there (not drawn, off the frame, "
                           f"or under {SEEN_MIN} of its height): a promise hangs on a thing a stranger can point at in THAT still")
    return out


MEASURED = {"moves", "comes", "goes", "grows", "falls", "rises", "breaks", "opens"}   # the plan's `how` words a box can show


def _declared(plan_stills, i, label):
    """does the plan's still i (0-based) name a change to this thing"""
    if i >= len(plan_stills):
        return False
    return any(ch.get("what") == label and str(ch.get("cause") or "").strip() for ch in plan_stills[i].get("new") or [])


def check(data, cam, nf, S, plan=None, name="shot", out=None, fps=30):
    """the RECIPE lines of one shot; True when its four stills have the recipe's shape. Writes the facts to `out`."""
    facts = collect(data, cam, nf, S, plan, fps=fps)
    probs = problems(facts, plan)
    st = facts["stills"]
    print(f"RECIPE {name}: his size on the four stills " + ", ".join(f"{s['data']['h']:.2f}" for s in st)
          + "; face off the lens " + ", ".join(f"{s['data']['face_deg']:.0f}" for s in st)
          + "; pose turns " + ", ".join(f"{pose_turn(st[i]['data']['pose'], st[i + 1]['data']['pose']):.0f}" for i in range(len(st) - 1))
          + f"; {len(facts['groups'])} declared things" + ("" if plan else "; no plan for this shot")
          + f" -> {'OK' if not probs else 'FAIL'}", flush=True)
    for p in probs:
        print(f"RECIPE {name}: {p}", flush=True)
    if out:
        try:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            json.dump(dict(facts, problems=probs), open(out, "w"), indent=1)
        except OSError:
            pass
    return not probs
