"""recipe_cases: the staging helper (store/recipe_stage.py) proven on seven prop shapes. Not a story anyone posts: each
shot is one way a shot's prop can be (a small thing he picks up, a crate he works, a crate he shoves away, a tall
post worked by its lever, a lever over his reach worked from a step, a small crate he walks across the frame, a
thing on the ground worked with a tool), built through store/shots.py by store/recipe_prove.py with no render, and
held to every check the harness prints. The props are plain boxes on purpose: the proof is his body and the frame."""
import locations as LOC, recipe_stage, shot_plan

WOOD = lambda: K.mat("case wood", "#8A5A2B")
IRON = lambda: K.mat("case iron", "#3A3D42", rough=0.5, metal=0.6)
RED = lambda: K.mat("case red", "#B23A2E")
AT = (0.1, -0.6, 0.0)                     # every prop stands here


def _ret(light, data, grips, conseq):
    return dict(lanes=[], kiosks=[], place="field", light=light, data=data, rest=1, grips=grips, cutaway=None, boxes=[], conseq=conseq)


def _st(n, size, **kw):
    st = recipe_stage.from_plan(shot_plan.shot(STORY, n), prop_at=AT, prop_size=size, **kw)
    if not st["ok"]: raise SystemExit(f"shot {n}: " + st["why"])
    print("STAGE", {k: st.get(k) for k in ("data_at", "yaw", "frame_h", "face_at", "chest_deg", "bearing", "grab", "reach", "step", "travel")}, flush=True)
    return st


def _slide(o, home, t0, t1, by):
    for f in range(int(round(t0 * FPS)), int(round(t1 * FPS)) + 1):
        u = max(0.0, min(1.0, (f / FPS - t0) / max(1e-6, t1 - t0))); key_loc(o, f / FPS, home + Vector(by) * (u * u * (3 - 2 * u)))


def shot1():
    """a small thing he picks up: a 0.2 m bulb off a stump"""
    light = LOC.field(); size = (0.3, 0.3, 0.3)
    stump = K.box("stump", (AT[0], AT[1], 0.15), size, WOOD())
    bulb = K.box("bulb", (AT[0] - 0.12, AT[1] - 0.04, 0.4), (0.1, 0.1, 0.2), RED())           # at the edge of the stump nearest him
    st = _st(1, (0.3, 0.3, 0.5), handle=(AT[0] - 0.18, AT[1] - 0.04, 0.36))     # the stump and the bulb on it are the thing in the frame
    data = load_data(); recipe_stage.place(data, st)
    T = recipe_stage.perform(data, st, DUR, grip=Vector(st["grab"]), pick=True)
    data.finish(); recipe_stage.carry(data, [bulb], T); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("bulb",), [("the bulb comes up off the stump in his hand", [stump, bulb], T["action"], DUR, {"moves": [bulb]})])


def shot2():
    """a crate he works: he shoves it a hand's width and its lid jumps (the thing under his hand MOVES: staging.cause)"""
    light = LOC.field(); size = (0.5, 0.4, 0.5)
    crate = K.box("crate", (AT[0], AT[1], 0.25), size, WOOD())
    lid = K.box("crate lid", (AT[0] + 0.08, AT[1], 0.52), (0.3, 0.36, 0.04), IRON())
    st = _st(2, size)
    data = load_data(); recipe_stage.place(data, st)
    home = Vector(crate.location); TT = st["times"]; a, r = TT["action"] * DUR, TT["release"] * DUR
    held = lambda t: Vector((0.06, 0.02, 0.0)) * (lambda u: u * u * (3 - 2 * u))(max(0.0, min(1.0, (t - a - 0.1) / (r - a - 0.1))))
    T = recipe_stage.perform(data, st, DUR, grip=lambda t: Vector(st["grab"]) + held(t))
    for f in range(int(a * FPS), int(r * FPS) + 1): key_loc(crate, f / FPS, home + held(f / FPS))
    _slide(lid, Vector(lid.location), T["action"] + 0.2, T["release"], (0.06, 0.02, 0.28))
    data.finish(); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("crate",), [("the lid jumps off the crate", [crate, lid], T["action"], DUR, {"moves": [lid]})])


def shot3():
    """a 0.62 m crate he shoves away from the lens"""
    light = LOC.field(); size = (0.5, 0.4, 0.62)
    crate = K.box("crate", (AT[0], AT[1], 0.31), size, WOOD())
    st = _st(3, size)
    data = load_data(); recipe_stage.place(data, st)
    home = Vector(crate.location); TT = st["times"]; a, r = TT["action"] * DUR, TT["release"] * DUR
    held = lambda t: Vector((0.0, 0.1, 0.0)) * (lambda u: u * u * (3 - 2 * u))(max(0.0, min(1.0, (t - a - 0.1) / (r - a - 0.1))))
    T = recipe_stage.perform(data, st, DUR, grip=lambda t: Vector(st["grab"]) + held(t))
    for f in range(int(a * FPS), int(r * FPS) + 1): key_loc(crate, f / FPS, home + held(f / FPS))
    _slide(crate, home + Vector((0.0, 0.1, 0.0)), T["release"], T["result"], (0.09, 0.22, 0.0))
    data.finish(); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("crate",), [("the crate slides away", [crate], T["action"], DUR, {"moves": True})])


def _post(handle_z):
    post = K.box("post", (AT[0], AT[1], 0.75), (0.14, 0.14, 1.5), IRON())
    lever = K.box("post lever", (AT[0] - 0.13, AT[1] - 0.05, handle_z), (0.16, 0.05, 0.05), RED())
    arm = K.box("signal arm", (AT[0] + 0.22, AT[1] - 0.09, 1.1), (0.3, 0.04, 0.1), RED())      # on the far side of the post from him: clear of his head when he is up on the step
    return post, lever, arm


def _lever(n, handle_z):
    light = LOC.field(); size = (0.14, 0.14, 1.5)
    post, lever, arm = _post(handle_z)
    st = _st(n, size, handle=(AT[0] - 0.2, AT[1] - 0.05, handle_z))
    if st.get("step"):
        K.box("step", (st["step"]["at"][0], st["step"]["at"][1], st["step"]["size"][2] / 2), st["step"]["size"], WOOD())
    data = load_data(); recipe_stage.place(data, st)
    home = Vector(lever.location); TT = st["times"]; a, r = TT["action"] * DUR, TT["release"] * DUR
    pull = lambda t: Vector((0.0, 0.0, -0.06)) * (lambda u: u * u * (3 - 2 * u))(max(0.0, min(1.0, (t - a - 0.1) / (r - a - 0.15))))
    T = recipe_stage.perform(data, st, DUR, grip=lambda t: Vector(st["grab"]) + pull(t))
    for f in range(int(a * FPS), int(r * FPS) + 1): key_loc(lever, f / FPS, home + pull(f / FPS))
    _slide(arm, Vector(arm.location), T["action"] + 0.25, T["release"], (0.0, 0.0, 0.3))
    data.finish(); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("post lever",), [("the signal arm goes up the post", [post, lever, arm], T["action"], DUR, {"moves": [arm]})])


def shot4():
    """a tall post worked by its lever, at his hand height"""
    return _lever(4, 0.38)


def shot5():
    """the same lever over his reach: he works it from a step"""
    return _lever(5, 0.82)


def shot6():
    """a small crate he walks across the frame: a push longer than a planted hand carries"""
    light = LOC.field(); size = (0.25, 0.25, 0.45)
    crate = K.box("crate", (AT[0], AT[1], 0.225), size, WOOD())
    st = _st(6, size, travel=(0.22, 0.0))
    data = load_data(); recipe_stage.place(data, st)
    home = Vector(crate.location)
    T = recipe_stage.perform(data, st, DUR, grip=Vector(st["grab"]))
    for f in range(int(T["action"] * FPS), int(T["release"] * FPS) + 2): key_loc(crate, f / FPS, home + T["moved"](f / FPS))
    data.finish(); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("crate",), [("the crate goes across the field with him", [crate], T["action"], DUR, {"moves": True})])


def shot7():
    """a thing on the ground, worked with a tool: he prods a puddle with a stick and it spreads"""
    light = LOC.field(); size = (0.6, 0.4, 0.02)
    puddle = K.cyl("puddle", (AT[0], AT[1], 0.012), 0.2, 0.02, K.mat("case water", "#2F5D8A", rough=0.15))
    st = _st(7, size, handle=(AT[0] - 0.2, AT[1] - 0.1, 0.0))
    data = load_data(); recipe_stage.place(data, st)
    T = recipe_stage.perform(data, st, DUR, grip=Vector(st["grab"]), tool=True)
    data.sc.frame_set(1); hand = data.arm.matrix_world @ data.pb[f"hand.{T['hand']}"].tail
    stick = K.cyl("stick", (hand.x, hand.y, hand.z - 0.12), 0.012, 0.34, WOOD())
    ripple = K.cyl("ripple", (AT[0] - 0.12, AT[1] - 0.06, 0.03), 0.05, 0.012, K.mat("case ripple", "#9CC7E8", rough=0.1))
    _slide(ripple, Vector(ripple.location), T["action"] + 0.2, T["result"], (0.3, 0.04, 0.0))       # it runs out from where the stick went in
    for t, sc_ in ((T["action"] + 0.2, 1.0), (T["result"], 1.9)):
        puddle.scale = (sc_, sc_, 1.0); puddle.keyframe_insert("scale", frame=int(round(t * FPS)) + 1)
    data.finish(); recipe_stage.carry(data, [stick], T); recipe_stage.frame(data, st, DUR)
    return _ret(light, data, ("stick",), [("the puddle spreads across the soil", [puddle, ripple], T["action"], DUR, {"moves": [ripple], "whole": True, "hero": False})])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5, 6: shot6, 7: shot7}
