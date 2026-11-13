"""THE BANANA SHORT (the second 3D short, 2026-11-12): every banana here is a clone, and a fungus is coming for it.
Made end to end without a storyboard sign-off (caaleb, 2026-11-12: "get it done without me having to say anything,
and then for me to give it my stamp of approval"), to the brief that came with it: the realistic store stays, Data
stays the cartoon, and he is IN the world through light, contact, consequence and eye-lines; MEDIUM shots and
close-ups only (no tiny Data); every beat shows its one fact; the video ends ON its payoff.

  1 hook     "nearly every banana here is a clone, and a fungus is coming for it": a medium close on Data at the
             produce table, a bright bunch in his hands going black as he holds it; a finger drops off onto the table
             and he holds the bunch away from himself.
  2 clones   "copies of one plant ... what kills one can kill them all": a rail of identical bunches on hooks, each
             with the same sticker; he pushes the first and every bunch swings in turn, the same swing down the row.
  3 before   "in the 1950s a soil fungus wiped out ... the Gros Michel": an old crate stencilled GROS MICHEL 1950; he
             lifts the lid and the fruit inside is black; he tips the crate and the dead fruit spills onto the floor.
  4 now      "a new strain ... no cure ... sits in the soil for decades": a young banana plant in a planter of soil;
             the rot climbs its stem from the soil and its leaves droop and brown while he holds one up in vain.
  5 payoff   "now it's in Ecuador ... no banana to switch to": the rail again; the bunches go black one after another
             toward him; he lifts the LAST yellow bunch off its hook and hugs it, the camera pushing in.

Run through the shot harness (store/shots.py, STORY=banana)."""
import produce as PR

TABLE = Vector((0.0, -0.3, 0.0))      # the produce table, centre of its footprint
TABLE_H = 0.3                          # a low produce table: its top sits below his chest, in frame under the bunch
RAIL_Y, RAIL_Z = -0.22, 0.52           # the hanging rail (shots 2 and 5)


def produce_set(lanes_x=(2.4, 3.0)):
    """the approved store, with the produce stand at the front; two lanes stay far off to the right of frame so the
    room still reads as the same supermarket"""
    lanes, kiosks, clerks = build_set(list(lanes_x), ())
    return lanes, kiosks


import locations as LOC


def place(name):
    """build one of the places in store/locations.py; returns the fields a shot hands the harness"""
    return dict(lanes=[], kiosks=[], place=name, light=LOC.PLACES[name]())


def soft_key(name, at, aim, energy=30, size=26, color=(1.0, 0.95, 0.86)):
    """a SPOT on a prop from the camera side: it lifts the fruit off the busy store without washing his teal pale"""
    ld = bpy.data.lights.new(name, 'SPOT'); ld.energy = energy; ld.spot_size = math.radians(size); ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.15; ld.color = color
    o = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(o); o.location = at
    o.rotation_euler = (Vector(aim) - Vector(at)).to_track_quat('-Z', 'Y').to_euler()
    return o


def follow(obj, fn, t0=0.0, t1=None, rot_fn=None):
    """key an object (a held bunch) onto a moving point every frame"""
    for f in range(F(t0), F(t1 if t1 is not None else DUR) + 1):
        t = (f - 1) / FPS; obj.location = fn(t); obj.keyframe_insert("location", frame=f)
        if rot_fn: obj.rotation_euler = rot_fn(t); obj.keyframe_insert("rotation_euler", frame=f)


def reach(data, side, fn, t0, t1, lead=0.4, back=0.45, elbow_out=0.45):
    """ONE HAND DOES A JOB, and only then: the arm hangs relaxed (FK, Data.RELAXED: the hand clear of the coat), swings
    to the job over `lead`, is ON the moving point fn(t) every frame of t0..t1, and falls back relaxed over `back`.
    (An IK 'hang' point kept the mitten 3 cm inside his coat on every idle frame: the clipping check found it.)"""
    bones = (f"arm.{side}", f"fore.{side}", f"hand.{side}")
    for b in bones:
        if not data._has_keys(data.arm, f'pose.bones["{b}"].rotation_euler'): data._k(b, 0.0, rot=data.RELAXED[b])
        data._k(b, max(0.0, t0 - lead), rot=data._pose_now(b, max(0.0, t0 - lead)) if t0 - lead > 0.05 else data.RELAXED[b])
    for f in range(F(t0), F(t1) + 1):
        t = (f - 1) / FPS; sc.frame_set(f); data._arm_ik(side, Vector(fn(t)), t, elbow_out)
    for b in bones: data._k(b, t1 + back, rot=data.RELAXED[b])


def drop(obj, t_drop, floor_z, kick=(0, -0.25, 0.25), spin=(5, 2, 7), bounce=0.25):
    """floor_z: a height, or fn(x, y) -> the height of what is under that point (a table top, then the floor past its edge)"""
    return _drop(obj, t_drop, floor_z if callable(floor_z) else (lambda x, y, z0=floor_z: z0), kick, spin, bounce)


def _drop(obj, t_drop, floor_at, kick, spin, bounce):
    """an object that is part of something lets go at t_drop: from its world pose it falls under gravity, lands on
    floor_z, bounces once and comes to rest lying down. Its parent link is cut so it keeps the world pose."""
    sc.frame_set(F(t_drop)); bpy.context.view_layer.update()
    M = obj.matrix_world.copy(); obj.parent = None; obj.matrix_world = M
    p0 = M.translation.copy(); r0 = M.to_euler(); v = Vector(kick); w = Vector(spin); g = 9.8
    own = bool(obj.animation_data and obj.animation_data.action)     # a thing he was carrying keeps its own path up to the drop
    for f in range(1, F(t_drop) + 1):
        if own: break
        obj.location = p0; obj.rotation_euler = r0; obj.keyframe_insert("location", frame=f); obj.keyframe_insert("rotation_euler", frame=f)
    obj.location = p0; obj.rotation_euler = r0; obj.keyframe_insert("location", frame=F(t_drop)); obj.keyframe_insert("rotation_euler", frame=F(t_drop))
    p, landed, t = p0.copy(), 0, t_drop
    for f in range(F(t_drop) + 1, NF + 1):
        dt = 1 / FPS; t += dt
        if landed < 2:
            v.z -= g * dt; p += v * dt
            fz = floor_at(p.x, p.y)
            if p.z <= fz + 0.012:
                p.z = fz + 0.012; landed += 1; v = Vector((v.x * 0.5, v.y * 0.5, -v.z * bounce)); w *= 0.4
                if landed == 2: v = Vector((0, 0, 0))
            r = Vector((r0.x, r0.y, r0.z)) + w * (t - t_drop)
            if landed == 2: r.x = math.radians(90) * round(r.x / math.radians(90)); r.y = 0      # it settles lying on the board
        obj.location = p; obj.rotation_euler = tuple(r); obj.keyframe_insert("location", frame=f); obj.keyframe_insert("rotation_euler", frame=f)


# ================================================================ SHOT 1: the hook
def shot1():
    """THE SHOCK FIRST (CLAUDE.md, "the opening is the shock"): a medium CLOSE on Data at the produce table holding a
    clean bright-yellow bunch up in both hands. Black patches creep over it (yellow showing between them, so it stays a
    bunch of BANANAS); at 0.9 s a finger pops off and hits the table; on that impact he RECOILS IN THE PICTURE PLANE:
    his body jerks back and sideways away from it, the arms shove the bunch out to full straight-arm length toward the
    lens, brows up. It keeps rotting and trembling in his outstretched hands; he shoots us a look; a second finger
    drops, he flinches harder and turns his face away squinting, then looks back to us, alarmed, to the end."""
    lanes, kiosks = produce_set()
    PR.table("produce table", (0.0, -0.36, 0.0), w=1.1, d=0.36, h=TABLE_H)
    # a BARE table: bunches laid along it were cut by the frame edges in every frame and read as clutter (judge, take 2)
    hm = PR.skin_mat("hero")
    # take 5 (judge 60): "once it goes black it reads as a black glove", "the dropped one lands as a flat black slug".
    # The rot is now PATCHES over yellow: the spots are a deep brown-black, and the whole-skin darkening only starts
    # far past where this shot takes the rot, so the yellow and every finger's shape stay readable to the end.
    try:
        for n_ in hm.node_tree.nodes:
            if n_.type == 'MAP_RANGE':
                n_.inputs["From Min"].default_value = 0.5; n_.inputs["From Max"].default_value = 1.6
            if n_.type == 'MIX':
                a_ = [s_ for s_ in n_.inputs if s_.name == "A" and s_.type == 'RGBA' and s_.is_linked]
                if a_ and a_[0].links[0].from_node.type == 'VALTORGB':
                    for s_ in n_.inputs:
                        if s_.name == "B" and s_.type == 'RGBA': s_.default_value = (*K.lin("#22140B"), 1)
    except (KeyError, AttributeError, IndexError, TypeError):
        pass
    hero, fingers = PR.bunch("hero bunch", (0, 0, 0), hm, n=6, seed=3, L=0.24, spread=1.0)
    data = load_data()
    data.place(0.0, 0.02, 0)
    sc.frame_set(1); bpy.context.view_layer.update()
    sh0 = {s_: acts._shoulder(data, s_) for s_ in "LR"}
    mid = (sh0["L"] + sh0["R"]) / 2
    T_DROP, T_REC, T_US, T_DROP2, T_FL2, T_BACK, T_DROP3, T_END = 0.85, 1.05, 1.7, 2.2, 2.4, 3.15, 3.75, 4.25
    # judge 62: "the bunch sits right under his chin and covers his mouth": held 7 cm lower, at his chest
    P0 = mid + Vector((0.02, -0.17, -0.04))
    P1 = mid + Vector((0.10, -0.32, -0.08))      # beyond his reach on purpose: the reach clamp below makes the arms STRAIGHT
    # take 5: "the recoil never happens ... his body doesn't pull back". A lean straight back is invisible from a lens
    # in front of him, so the flinch goes back AND sideways, away from the bunch: his head travels across the frame
    # while the bunch goes the other way, out to full arm's length. The bend directions are MEASURED on the rig.
    def head_with(rx, rz):
        data.pb["spine"].rotation_euler = (math.radians(rx), 0, math.radians(rz)); bpy.context.view_layer.update()
        return (data.arm.matrix_world @ data.pb["head"].head).copy()
    h0 = head_with(0, 0); BK = -1 if (head_with(-10, 0) - h0).y > 0 else 1; SD = -1 if (head_with(0, 10) - h0).x > 0 else 1
    data.pb["spine"].rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
    # judge 62: "the recoil never happens ... a slight lean": a BIG jerk on impact that overshoots and settles, and a
    # fresh flinch on every finger that goes, so nothing holds still after the payoff
    lean = [(0.0, 0, 0), (T_REC, 0, 0), (T_REC + 0.13, 25, 17), (T_REC + 0.45, 19, 12),
            (T_DROP2 + 0.12, 18, 12), (T_FL2 + 0.13, 27, 19), (T_FL2 + 0.45, 21, 14),
            (T_DROP3 + 0.1, 20, 13), (T_DROP3 + 0.25, 26, 18), (T_DROP3 + 0.55, 22, 15), (DUR, 22, 15)]
    for t_, b_, s_ in lean:
        data._k("spine", t_, rot=(BK * b_, 0, SD * s_)); data._k("chest", t_, rot=(BK * b_ * 0.45, 0, SD * s_ * 0.45))
    REACH = 0.995 * (data.U + data.Fo)
    out = lambda t: ease((t - T_REC) / 0.26)
    def hand_off(s_, c):
        sx = -1 if sh0[s_].x < mid.x else 1
        return c + Vector((sx * 0.05 - 0.01, 0.02, -0.04 if sx > 0 else -0.01))
    # the fan spread flat to the lens so every finger is its own shape (fingers at the lens fanned into one blob)
    tilt = lambda t: Vector((math.radians(90), math.radians(-38 - 10 * out(t)), 0))
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
        c = P0.lerp(P1, out(t))
        shake = min(1.0, max(0.0, (t - T_REC - 0.25) / 0.3))           # it trembles in his outstretched hands
        c = c + Vector((0.005 * math.sin(2 * math.pi * 9 * t), 0, 0.005 * math.sin(2 * math.pi * 11 * t + 1))) * shake
        for _ in range(10):                                            # held at his reach, never past it
            worst = None
            for s_ in "LR":
                d_ = hand_off(s_, c) - sh[s_]
                if d_.length > REACH and (worst is None or d_.length - REACH > worst[0]): worst = (d_.length - REACH, d_)
            if worst is None: break
            c = c - worst[1].normalized() * (worst[0] + 1e-4)
        hero.location = c; hero.keyframe_insert("location", frame=f)
        hero.rotation_euler = tuple(tilt(t) + Vector((0.035 * math.sin(2 * math.pi * 7 * t), 0, 0)) * shake)
        hero.keyframe_insert("rotation_euler", frame=f)
        for s_ in "LR":
            data._arm_ik(s_, hand_off(s_, c), t, 0.4)
    # the rot: a clean bright bunch on frame one, patches spreading all through the shot (it never stops)
    rv = PR.rot_node(hm)
    for t_, v_ in ((0.0, 0.1), (0.15, 0.12), (T_DROP, 0.45), (T_FL2, 0.56), (DUR, 0.64)):
        rv.default_value = v_; rv.keyframe_insert("default_value", frame=F(t_))
    # judge 62: "the dropped banana lands as a large dark log ... a sausage": a finger that has left the bunch stops
    # rotting where it was, so it lies on the table a spotted YELLOW banana, not a black slug (own material per object)
    def own_rot(fo, t_hold):
        try:
            m_ = hm.copy(); rv_ = PR.rot_node(m_)
            hold = min(0.42, 0.1 + 0.32 * t_hold / T_DROP)
            for t_, v_ in ((0.0, 0.1), (0.15, 0.12), (t_hold, hold), (DUR, hold)):
                rv_.default_value = v_; rv_.keyframe_insert("default_value", frame=F(t_))
            sl_ = fo.material_slots[0]; sl_.link = 'OBJECT'; sl_.material = m_
        except (KeyError, AttributeError, IndexError, TypeError, RuntimeError):
            pass
    # fingers that go later keep their own world path while still on the bunch (drop() freezes an un-keyed one)
    def bake(fo, t_go):
        Ms = []
        for f in range(1, F(t_go) + 1):
            sc.frame_set(f); bpy.context.view_layer.update(); Ms.append(fo.matrix_world.copy())
        fo.parent = None; prev = None
        for f, M_ in enumerate(Ms, 1):
            e_ = M_.to_euler('XYZ', prev) if prev else M_.to_euler('XYZ'); prev = e_
            fo.location = M_.translation; fo.rotation_euler = e_
            fo.keyframe_insert("location", frame=f); fo.keyframe_insert("rotation_euler", frame=f)
    f2, f3 = fingers[3], fingers[5]
    bake(f2, T_DROP2); bake(f3, T_DROP3)
    def bunch_at(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update(); return hero.matrix_world.translation.copy()
    sc.frame_set(1); bpy.context.view_layer.update()
    US = (0.0, -2.0, 0.7)
    data.look_at(P0 + Vector((0, 0, 0.08)), 0.0, max_yaw=30, blend=0.0)
    data.look_at((P0.x + 0.1, P0.y - 0.04, TABLE_H + 0.05), T_DROP + 0.15, max_yaw=30)     # his eyes follow it down
    data.look_at(bunch_at(T_REC + 0.3) + Vector((0, 0, 0.1)), T_REC + 0.15, max_yaw=30)     # then the thing in his hands
    data.look_at(US, T_US, max_yaw=30)                                                     # to us: are you seeing this?
    data.look_at(bunch_at(T_DROP2) + Vector((0, 0, 0.05)), T_DROP2 + 0.05, max_yaw=30)      # another one goes
    data.look_at((-0.45, -1.7, 0.78), T_FL2 + 0.12, max_yaw=30)                             # he turns his face away
    data.look_at(US, T_BACK, max_yaw=30)                                                   # back to us
    data.look_at(bunch_at(T_DROP3) + Vector((0, 0, 0.05)), T_DROP3 + 0.05, max_yaw=30)      # and ANOTHER goes
    data.look_at(US, T_END, max_yaw=30)                                                    # to us, alarmed, to the end
    data.expression("worried", 0.45)
    data.expression("alarmed", T_REC, blend=0.08)
    A_ = data.EXPRESSIONS["alarmed"]
    W_ = dict(brow=0.16, lid=0.38, frown=1.0)                                              # the wince
    data._face(T_FL2, **A_); data._face(T_FL2 + 0.12, **W_); data._face(T_BACK - 0.2, **W_)
    data._face(T_BACK + 0.05, **A_); data._face(T_DROP3, **A_); data._face(T_DROP3 + 0.12, **W_)
    data._face(T_END - 0.15, **W_); data._face(T_END + 0.05, **A_); data._face(DUR, **A_)
    data.blink(0.6)   # no blink late in the shot: the end blink glitched the eyes into rings behind the lenses (frame 24)
    data.finish()
    # judge 62: the first finger landed "across the table at his waist, hiding his lower body": every finger now pops
    # off toward image right, the side the bunch is held out to, clear of his body, with a visible bounce
    own_rot(fingers[0], T_DROP); own_rot(f2, T_DROP2); own_rot(f3, T_DROP3)
    drop(fingers[0], T_DROP, TABLE_H + 0.034, kick=(0.45, -0.1, 1.0), spin=(2, 0.5, 4), bounce=0.45)
    drop(f2, T_DROP2, TABLE_H + 0.034, kick=(0.15, -0.08, 0.7), spin=(-2, 0.4, 3), bounce=0.45)
    drop(f3, T_DROP3, TABLE_H + 0.034, kick=(0.25, -0.06, 0.8), spin=(2, -0.4, 3), bounce=0.45)
    soft_key("bunch key", (0.5, -1.0, 0.9), tuple(P0), energy=24, size=26)
    # a medium close (30 mm) that JOLTS in 5 cm with his recoil (the camera reacts with him), then holds
    C0, LK = Vector((0.05, -1.0, 0.66)), Vector((mid.x + 0.02, -0.1, 0.51))
    cam = K.camera(tuple(C0), tuple(LK), lens=30, fstop=3.2)
    camera_path(cam, lambda t: (C0 + Vector((0, 0.05 * ease((t - T_REC) / 0.2), 0)), LK, P0))
    rest_f = [fo for k, fo in enumerate(fingers) if k not in (0, 3, 5)]
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("hero bunch",),
                conseq=[("the bunch goes black in his hands", rest_f, 0.0, T_DROP2),
                        ("a finger drops onto the table", [fingers[0]], T_DROP, DUR),
                        ("a second finger drops", [f2], T_DROP2, DUR)])


# ================================================================ the rail (shots 2 and 5)
RAIL0, RAIL_YAW, RAIL_LEN, N_HOOK = (-0.2, -0.8), 40, 1.0, 6      # it runs from just in front of him to the right and back: diagonal to the lens, and he faces us over it


# where he stands for the rail beats: BESIDE the rail's near end, level with it, turned a little to it, so the row runs away
# behind his shoulder and nothing on it ever hangs between his face and the lens (the first layout stood him behind
# the rail with a bunch over his face for the whole beat: staging.face_hidden now refuses that)
RAIL_DP, RAIL_DROT = Vector((-0.38, -0.8, 0)), 20
RAIL_C0, RAIL_LK = Vector((-0.16, -1.72, 0.6)), Vector((-0.22, -0.6, 0.47))   # Data's whole head in frame, the rail running off to the right   # the row seen at 45 deg, every bunch its own shape, running on out of frame   # him on the left third, the row receding past his shoulder to the right


# shot 2's own rail (take 4): the judge, take 3: "the rail is cut by the left frame edge in every frame", "his hands
# stay at his sides", "TINY DATA". Now the row starts AT his left hand, centre frame, and runs back and to the right at
# 38 deg to the lens, so all six bunches fit in the frame, getting smaller toward the far post. Data stands at its near
# end, frame left, turned to us, his arm out to the first bunch. The near post sits 9 cm clear of his arm.
S2_YAW = 52                                       # rail direction (0.616, 0.788): back and to the right
S2_HOOK0 = Vector((0.17, -0.55, 0))               # the first hook, just off his left hand
S2_R0, S2_YAW = (0.12, -0.62), 242
S2_DP, S2_DROT = Vector((0.3, -0.5, 0)), -14
S2_C0, S2_LK = Vector((0.04, -2.05, 0.6)), Vector((0.1, -0.8, 0.44))


def rail_row(m_of, sticker=True, r0=None, yaw=None, n=None, length=None, L=0.16):
    """the hanging rail with a bunch on every hook; m_of(k) -> that bunch's skin. Every bunch carries the SAME blue
    sticker: the one fact of the beat (copies of one plant) on the fruit itself, not on a sign over it."""
    r0 = r0 or RAIL0; yaw = RAIL_YAW if yaw is None else yaw; n = n or N_HOOK; length = length or RAIL_LEN
    pivot, hooks = PR.rail_at("banana rail", r0, yaw, length, RAIL_Z, n)
    blue = K.mat("sticker", "#1F5FA8", rough=0.4); ink = K.mat("sticker ink", "#FFFFFF", rough=0.4)
    rows = []
    for k, (p, sw) in enumerate(hooks):
        root, fingers = PR.hang_bunch(f"rail bunch {k}", sw, m_of(k), seed=40 + (k % 2), L=L)   # two seeds only: the bunches are COPIES
        if sticker:
            f0 = fingers[2]; bpy.context.view_layer.update()
            st = K.cyl(f"sticker {k}", (0, 0, 0), 0.022, 0.002, blue, v=20, bev=0)
            st.parent = f0; st.matrix_parent_inverse = Matrix.Identity(4); st.location = (0.075 * 0.16 / 0.13, 0, 0.0); st.rotation_euler = (math.radians(90), 0, 0)
            st.location.z += 0.02 * 0.16 / 0.13
        rows.append((p, sw, root, fingers))
    sign = K.box("rail sign", (0, 0, 0), (0.44, 0.012, 0.11), K.mat("rail sign board", "#F4EFE4", rough=0.5), bev=0.004)
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z'); mid = Vector((r0[0], r0[1], 0)) + R @ Vector((length * 0.5, 0, 0))
    sign.location = (mid.x, mid.y, RAIL_Z + 0.16); sign.rotation_euler = (0, 0, math.radians(yaw))
    K.text("rail sign text", "CAVENDISH", tuple(Vector((mid.x, mid.y, RAIL_Z + 0.16)) + R @ Vector((0, -0.0075, 0))), 0.06,
           (math.radians(90), 0, math.radians(yaw)), K.mat("rail sign ink", "#1F5FA8", rough=0.5), extrude=0.001)
    for xp in (0.0, length):
        c = Vector((r0[0], r0[1], 0)) + R @ Vector((xp, 0, 0))
        K.cyl("sign wire", (c.x, c.y, RAIL_Z + 0.11), 0.002, 0.1, K.mat("rail chrome"), v=6, bev=0)
    return rows


# ================================================================ SHOT 2: clones
def shot2():
    """COPIES OF ONE PLANT, AND WHAT KILLS ONE KILLS THEM ALL. A three-quarter shot DOWN the rail: the first bunch hangs
    big in the foreground with its blue sticker readable, Data beside it with his hand ON it, and the row of identical
    bunches (the same sticker on every one) recedes behind. He pushes it and the swing runs down the row, every bunch
    the same swing; on "what kills one can kill them all" the rot starts on the bunch under his hand and jumps from
    bunch to bunch down the row, ending on the whole row black. (Judge, takes 2-6: the row behind him read as "tiny
    yellow shapes in the background", his hand pushed air, he hugged the frame edge.)"""
    where = place("warehouse")
    R0, YAW = (0.0, -1.08), 50                      # from beside him, straight away from the lens and a little right
    DP, DROT = Vector((-0.22, -0.84, 0)), 18          # beside the near end, turned a little to it, face to the lens
    T_PUSH, T_BLIGHT = 1.1, DUR * 0.52
    mats = [PR.skin_mat(f"rail {k}") for k in range(4)]
    rows = rail_row(lambda k: mats[k], sticker=False, r0=R0, yaw=YAW, n=4, length=0.66, L=0.19)   # four big copies, all in frame   # the sticker read as a blue ball under each bunch
    for k, (p, sw, root, fingers) in enumerate(rows):
        PR.swing(sw, T_PUSH + 0.2 * k, amp_deg=30, period=1.0, tau=1.6, nf=NF, across=True)
        PR.rot(mats[k], T_BLIGHT + 0.45 * k, T_BLIGHT + 0.45 * k + 0.8, to=0.62)
    data = load_data()
    data.place(DP.x, DP.y, DROT)
    sc.frame_set(1); bpy.context.view_layer.update()
    side = near_hand(data, rows[0][0])
    def on_bunch(t):                                  # the side of the first bunch that faces him, at its middle
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return rows[0][2].matrix_world.translation + Vector((-0.06, 0.0, -0.09))
    reach(data, side, lambda t: on_bunch(max(t, T_PUSH - 0.05)), T_PUSH - 0.5, T_PUSH + 0.3, lead=0.45, elbow_out=0.35)
    reach(data, side, lambda t: on_bunch(max(t, T_BLIGHT - 0.05)), T_BLIGHT - 0.5, T_BLIGHT + 0.25, lead=0.4, elbow_out=0.35)   # he touches it again: the rot starts under his hand
    data.look_at(rows[0][0] + Vector((0, 0, -0.1)), 0.3, max_yaw=38)
    data.look_at(rows[3][0], T_PUSH + 0.5, max_yaw=38)                 # the swing running away down the row
    data.look_at((DP.x + 0.1, -2.2, 0.75), T_PUSH + 1.5, max_yaw=25)    # to us: all the same plant
    data.look_at(rows[0][0] + Vector((0, 0, -0.1)), T_BLIGHT - 0.2, max_yaw=38)
    data.look_at(rows[3][0], T_BLIGHT + 1.0, max_yaw=38)               # it runs away from him down the row
    data.look_at((DP.x + 0.1, -2.2, 0.75), DUR - 1.0, max_yaw=25)      # to us: all of them
    data.idle(0.0, DUR)
    data.expression("happy", 0.2, T_BLIGHT - 0.3)
    data.expression("alarmed", T_BLIGHT + 0.1, DUR)
    data.blink(0.7); data.blink(T_BLIGHT - 0.6); data.blink(DUR - 0.5)
    data.finish()
    soft_key("rail key", (0.7, -1.6, 1.1), (0.05, -0.6, 0.5), energy=40, size=30)
    C0, C1 = Vector((-0.04, -1.88, 0.66)), Vector((-0.01, -1.8, 0.65)); LK = Vector((0.0, -0.55, 0.44))   # the whole row in frame, drifting toward it, not into his face
    cam = K.camera(tuple(C0), tuple(LK), lens=24, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, rows[1][0]))
    swingers = [r[2] for r in rows]
    return dict(**where, data=data, rest=1, grips=("rail bunch 0",),
                conseq=[("every bunch swings in turn", lambda: meshes(swingers), T_PUSH, T_PUSH + 1.6),
                        ("the blight runs down the row", lambda: meshes(swingers), T_BLIGHT, DUR)])


# ================================================================ SHOT 3: it happened before
def shot3():
    """THE GROS MICHEL. An old wooden crate on the table, GROS MICHEL / 1950 stencilled on it. He lifts its lid off and
    drops it aside: the fruit inside is fat and yellow for a beat, then goes black. He pushes the crate over on its
    side and the dead fruit spills out across the table."""
    where = place("plantation")
    PR.table("produce table", (-0.05, -0.42, 0.0), w=1.0, d=0.5, h=TABLE_H)
    TOP = TABLE_H + 0.034
    # he stands BESIDE the table's end, whole body in frame, and works the crate from its side (take 2 stood him
    # behind the table: "a floating head behind the crate ... teal feet poke out under the table")
    # take 5 (judge 58): "the tipped crate hangs past the table's front edge with nothing under it" and "covers Data's
    # whole body". The crate now sits far enough back that, tipped onto its face, its open top lands just INSIDE the
    # table edge: it RESTS on the table. It is a little narrower and the camera moved right, so the tipped crate stands
    # clear of him in this lens.
    EDGE_Y = -0.42 - 0.25                       # the table's front edge: past it the fruit falls to the floor
    CW, CD, CH = 0.40, 0.28, 0.19
    CX = 0.2; CY = EDGE_Y + 0.012 + CD / 2 + CH; cz = TABLE_H + 0.03
    cr = PR.crate("old crate", (CX, CY, cz), w=CW, d=CD, h=CH)
    piv = K.empty("crate tip", (CX, CY - CD / 2, cz)); root = cr["root"]          # it goes over FORWARD on its front bottom edge: its open top turns to the lens and the dead fruit pours out toward us (tipped sideways, the fruit fell inside the upright crate and vanished)
    root.parent = piv; root.matrix_parent_inverse = piv.matrix_basis.inverted()
    lid = cr["lid"]; lid_m = lid.matrix_world.copy(); lid.parent = None; lid.matrix_world = lid_m   # the lid comes OFF
    for nm_, dz_ in (("old crate stencil", 0.006), ("old crate year", -0.006)):   # the stencil reads at phone size (judge: "small and soft")
        o_ = bpy.data.objects.get(nm_)
        if o_: o_.scale = (1.3, 1.3, 1.3); o_.location.z += dz_
    gm = PR.skin_mat("gros michel", base="#E9C640", neck="#A9B23A")
    inside, crowns = [], []
    for k, (dx, dy, yaw) in enumerate(((-0.08, 0.05, 0.4), (0.08, 0.02, 2.7), (0.0, 0.07, -0.3))):   # toward the back and low: the stencil stays clear
        r_, fs = PR.bunch(f"gros bunch {k}", (CX + dx, CY + dy, cr["inner_z"] + 0.005), gm, n=4, seed=60 + k, L=0.14, spread=0.6, parent=root)
        r_.rotation_euler = (0, 0, yaw); inside += fs
        crowns += [c_ for c_ in r_.children if c_.type == 'MESH' and c_ not in fs]   # crowns and stems pour out too (judge: "green pieces stay stuck in the empty crate")
    # the crate is OPEN from frame one, its lid lying on the table beside it: lifting the lid ate a second and a half
    # before the rot even started (judge, take 2)
    T_ROT0, T_ROT1, T_TIP0, T_TIP1 = 0.25, 2.0, 3.05, 3.95
    lid.location = Vector(lid.location) + Vector((-CW / 2 - 0.22, -0.02, -CH + 0.0)); lid.rotation_euler = (0, 0, math.radians(8))
    PR.rot(gm, T_ROT0, T_ROT1, to=1.0)
    # take 4 (judge 50): "the crate pops toward camera in a single step, the tipping is never seen". Now it goes over
    # through every angle in about a second, and the camera sits front-left so the tip reads in profile
    # take 5: it lands flat on its face (90) with one small rebound and RESTS on the table (it used to hang at 88)
    for t, a_ in ((0.0, 0), (T_TIP0, 0), (T_TIP0 + 0.2, 6), (T_TIP0 + 0.45, 24), (T_TIP0 + 0.7, 58), (T_TIP1, 90),
                  (T_TIP1 + 0.12, 84), (T_TIP1 + 0.26, 90), (DUR, 90)):
        piv.rotation_euler = (math.radians(a_), 0, 0); piv.keyframe_insert("rotation_euler", frame=F(t))
    rnd = random.Random(5)
    under = lambda x, y: TOP if y > EDGE_Y else 0.0
    for i, fo in enumerate(inside + crowns):   # the dead fruit pours out of the open top, over the table's front edge, onto the floor
        drop(fo, T_TIP0 + 0.72 + 0.04 * i, under, kick=(rnd.uniform(-0.2, 0.2), rnd.uniform(-1.0, -0.75), 0.3), spin=(rnd.uniform(-5, 5), 2, rnd.uniform(-5, 5)), bounce=0.2)
    data = load_data()
    # take 4: "cut by the right edge for the whole shot", "his arm stretches into empty air short of the crate". He
    # now stands CLOSE at the crate's end (the table slid left to make room), turned to it and to the lens
    # take 5 (judge 58): "his hand never touches the crate ... it floats above the back edge". The IK target is the
    # WRIST, and it was put ON the edge, so the mitten hung over it. The wrists now sit just behind the back face, a
    # little under the top edge, so the mittens lie ON the back edge; and he is slid in until both grips are well
    # inside his reach on the planted frame (measured, not guessed).
    R = 0.995 * (data.U + data.Fo) * data.arm.scale.x
    BACK = CY + CD / 2 + 0.04; GZ = cz + CH - 0.012
    G_IN, G_OUT = CX + CW / 2 - 0.13, CX + CW / 2 - 0.03
    DX, DY = CX + CW / 2 + 0.17, CY + CD / 2 - 0.01        # at the crate's back corner, beside the table's end
    for _ in range(8):
        data.place(DX, DY, -34)
        sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
        inner, outer = sorted("LR", key=lambda s_: sh[s_].x)   # each hand on its own side, never crossed
        far = max((Vector((G_IN, BACK, GZ)) - sh[inner]).length, (Vector((G_OUT, BACK, GZ)) - sh[outer]).length)
        if far <= 0.82 * R or DX <= CX + CW / 2 + 0.11: break
        DX -= min(0.02, far - 0.82 * R)
    sc.frame_set(1); bpy.context.view_layer.update()
    # he LEANS into the shove (keyed before the IK, which is solved on the leaned pose), then rocks back from it
    data._k("spine", 0.0, rot=(0, 0, 0)); data._k("spine", T_TIP0 - 0.3, rot=(0, 0, 0))
    data._k("spine", T_TIP0 + 0.12, rot=(10, 0, 0)); data._k("spine", T_TIP0 + 0.45, rot=(13, 0, 0))
    data._k("spine", T_TIP0 + 0.95, rot=(-5, 0, 0)); data._k("spine", T_TIP0 + 1.4, rot=(0, 0, 0))
    sc.frame_set(1); bpy.context.view_layer.update()
    def edge_at(x_, t):           # a grip point on the crate's back edge, riding the tip
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return piv.matrix_world @ (root.matrix_parent_inverse @ Vector((x_, BACK, GZ)))
    # the hands stay ON the crate for every frame it is inside his reach (measured), then come DOWN to his sides by IK:
    # take 5's relaxed blend from the shove swung a forearm 11 cm through his head
    T_ON, T_OFF = T_TIP0 - 0.35, T_TIP0 + 0.1
    for f in range(F(T_TIP0), F(T_TIP0 + 0.5) + 1):
        t = (f - 1) / FPS
        sc.frame_set(f); bpy.context.view_layer.update()
        shf = {s_: acts._shoulder(data, s_) for s_ in "LR"}
        if max((edge_at(G_IN, t) - shf[inner]).length, (edge_at(G_OUT, t) - shf[outer]).length) > 0.97 * R: break
        T_OFF = t
    T_DOWN = T_OFF + 0.35
    def hand_path(x_, s_):
        def fn(t):
            if t <= T_OFF: return edge_at(x_, t)
            p0 = edge_at(x_, T_OFF)
            sc.frame_set(F(t)); bpy.context.view_layer.update()
            sh_ = acts._shoulder(data, s_); fw = data.forward()
            side = Vector((-fw.y, fw.x, 0)); side = side if side.dot(sh_ - data.pos()) > 0 else -side   # out to its own side
            rest = sh_ + side * 0.07 + fw * 0.05 + Vector((0, 0, -0.85 * R))
            return p0.lerp(rest, ease(min(1.0, (t - T_OFF) / (T_DOWN - T_OFF))))
        return fn
    reach(data, inner, hand_path(G_IN, inner), T_ON, T_DOWN, lead=0.4, back=0.3, elbow_out=0.55)
    reach(data, outer, hand_path(G_OUT, outer), T_ON, T_DOWN, lead=0.4, back=0.3, elbow_out=0.55)
    US = (0.22, -2.0, 0.8)
    data.look_at((CX, CY, cz + 0.1), 0.0, max_yaw=30, blend=0.0)
    data.look_at(US, T_ROT1 - 0.15, max_yaw=30)                          # to us: see?
    data.look_at((CX, CY, cz + 0.15), T_TIP0 - 0.4, max_yaw=30)
    data.look_at((CX - 0.05, -0.9, 0.05), T_TIP1 + 0.1, max_yaw=30)      # down at the dead fruit landing on the ground
    data.look_at(US, T_TIP1 + 1.0, max_yaw=30)                           # and back to us: gone, all of it
    data.idle(0.0, DUR)
    data.act("shrug", T_TIP1 + 1.25, dur=0.28, hold=0.55)                # nothing to be done
    # take 5: "holds static for about two seconds after the payoff": a slow shake of the head, still to us
    for k_, t_ in enumerate((T_TIP1 + 2.3, T_TIP1 + 2.55, T_TIP1 + 2.8)):
        if t_ < DUR - 0.1: data.look_at((US[0] + (0.28 if k_ % 2 == 0 else -0.28), US[1], US[2]), t_, max_yaw=30)
    if T_TIP1 + 3.05 < DUR: data.look_at(US, T_TIP1 + 3.05, max_yaw=30)
    data.expression("happy", 0.2, T_ROT0)
    data.expression("worried", T_ROT0 + 0.3, T_TIP0 + 0.6)
    data.expression("alarmed", T_TIP0 + 0.7, DUR)
    data.blink(1.1); data.blink(T_ROT1 + 0.5)
    data.finish()
    soft_key("crate key", (0.25, -1.3, 1.0), (CX, CY, cz + 0.08), energy=30, size=28)
    # take 5: from the front-LEFT the tipped crate stood between the lens and him. Now near-frontal, just left of him:
    # the crate, all of Data clear of it, and the ground in front of the table where the fruit lands
    C0, C1 = Vector((0.22, -2.0, 0.8)), Vector((0.24, -1.9, 0.77)); LK = Vector((0.34, -0.45, 0.4))
    cam = K.camera(tuple(C0), tuple(LK), lens=30, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, (CX, CY, cz + 0.1)))
    return dict(**where, data=data, rest=1, grips=("old crate", "gros bunch"),
                conseq=[("the fruit goes black", inside, T_ROT0, T_ROT1),
                        ("the crate goes over and the dead fruit spills", lambda: meshes([root] + inside + crowns), T_TIP0 + 0.2, DUR)])


# ================================================================ SHOT 4: the new strain
def shot4():
    """NO CURE, IN THE SOIL FOR DECADES. A young banana plant in a planter on the floor beside him. The rot climbs its
    stem out of the soil and its leaves droop and brown one after another. He takes hold of a drooping leaf and lifts it
    back up; he lets go and it flops down, dead."""
    where = place("field")
    # take 2 (judge, 50): "the plant is cut by the left frame edge in all 24 frames", "his hand only brushes the leaf
    # tips", "the leaves go dark and spotted rather than yellow", "at the end he just stands facing the camera". Now the
    # plant and its mound sit left of centre, Data close beside it, and the camera pulls back so BOTH are whole with
    # room; the leaves fan back and to the sides (nothing wide to the left to be cut); the leaves go YELLOW, then brown;
    # the lift is a big, slow move (sagged far down -> raised above level, held) and the drop has its own second; he
    # ends with his shoulders sagging and a sad look to us.
    # take 3 (judge, 63): "the background plants are already brown and dead", "the plant is small ... a dark spiky
    # clump, like a broom head", "his arm rests near the leaf tip rather than lifting it", "stiff and front-facing",
    # "frames 17-24 are a static hold". Now the field behind is HEALTHY green (this one plant dying is the story), the
    # plant is taller with bigger leaves and the camera low and closer, the leaves stay yellow (not black) as they hang,
    # he leans in and lifts the leaf from underneath to his eye line, it flops, he slumps and shakes his head, and the
    # timing is pushed late so the reaction fills the end while the camera keeps creeping in.
    try:   # heal the field: every dead tree gets the live skin and its leaves lifted back up
        stem_l, leaf_l, stem_ml, _ = LOC._tree_parts(False)
        for o in list(bpy.data.objects):
            if o.type != 'MESH': continue
            if o.data and o.data.name == "tree leaf dead":
                o.data = leaf_l; r = o.rotation_euler; o.rotation_euler = (r[0], r[1] - math.radians(55), r[2])
            elif o.material_slots and o.material_slots[0].material and o.material_slots[0].material.name == "tree stem dead":
                o.material_slots[0].material = stem_ml
    except (AttributeError, KeyError, TypeError, IndexError):
        pass
    PX, PY = -0.12, -0.42
    soil = LOC._noise_mat("field soil", "#5A4430", "#47362A")
    K.sph("young plant mound", (PX, PY, -0.03), 1.0, soil, scale=(0.19, 0.16, 0.09))   # planted in the field's own soil
    pt = PR.plant("young plant", (PX, PY, 0.02), height=0.55, seed=8, angles=(8, 150, 50, 128, 72, 104))   # to the side and back, none at the lens, none far out left
    for h_, _ in pt["leaves"]: h_.scale = (1.22, 1.22, 1.22)   # banana leaves big enough to read on a phone
    T_CLIMB0, T_CLIMB1 = 0.2, DUR * 0.62
    PR.rot(pt["stem_mat"], T_CLIMB0, T_CLIMB1, to=0.95)
    # take 4 (judge, 64): "the fungus is subtle: a few flecks, then the stem just turns dark" -> a thick dark fungal
    # SLEEVE grows up the stem out of the mound, its front edge plain to see; "yellow drooping leaves read as hanging
    # banana bunches" -> the leaves go DRY BROWN with black edges and collapse limp down the stem, never yellow.
    fung_m = LOC._noise_mat("banana fungus", "#2B1F24", "#4A2E2A", scale=22.0, rough=0.95, bump=0.5)
    FH = 0.55 * 0.8
    fpiv = K.empty("young plant fungus pivot", (PX, PY, 0.0))
    fung = K.cyl("young plant fungus", (PX, PY, FH / 2), 0.04, FH, fung_m, v=20, bev=0.0, parent=fpiv)
    for v_ in fung.data.vertices:   # follow the stem's taper, a little lumpy
        k_ = 1.0 - 0.33 * (v_.co.z / FH + 0.5) + 0.08 * math.sin(v_.co.z * 60 + math.atan2(v_.co.y, v_.co.x) * 3)
        v_.co.x *= k_; v_.co.y *= k_
    fpiv.scale = (1, 1, 0.03); fpiv.keyframe_insert("scale", frame=1); fpiv.keyframe_insert("scale", frame=max(1, F(T_CLIMB0)))
    for i in range(1, 9):
        u = i / 8; fpiv.scale = (1, 1, 0.03 + 0.97 * (u * u * (3 - 2 * u))); fpiv.keyframe_insert("scale", frame=F(T_CLIMB0 + (T_CLIMB1 - T_CLIMB0) * u))
    YEL, YEL_NECK = "#7E5E34", "#5E4628"           # dry dead brown (never banana yellow), darker at the neck

    def yellow(m, t0, t1):
        """key the leaf's own colour ramp from green to straw-yellow over t0..t1"""
        try:
            ramp = next(n for n in m.node_tree.nodes if n.type == 'VALTORGB')
            els = ramp.color_ramp.elements
            for el in els:
                if el.position > 0.97: continue                         # the leaf's dark tip stays as it is
                el.keyframe_insert("color", frame=1); el.keyframe_insert("color", frame=max(1, F(t0)))
                el.color = (*K.lin(YEL_NECK if el.position < 0.1 else YEL), 1); el.keyframe_insert("color", frame=max(2, F(t1)))
        except (StopIteration, TypeError, AttributeError, RuntimeError):
            pass
    # the leaf that points at him is the one he lifts; the others wilt in turn
    data = load_data()
    DP = Vector((0.25, -0.34, 0)); data.place(DP.x, DP.y, -14)
    sc.frame_set(1); bpy.context.view_layer.update()
    to_him = math.atan2(DP.y - PY, DP.x - PX)
    lifted = min(range(len(pt["leaves"])), key=lambda k: abs(((pt["leaves"][k][0].rotation_euler.z - to_him) + math.pi) % (2 * math.pi) - math.pi))
    hz, hm = pt["leaves"][lifted]
    hz.rotation_euler = (0, math.radians(-5), to_him)
    others = [k for k in range(len(pt["leaves"])) if k != lifted]
    for i, k in enumerate(others):
        h_, m_ = pt["leaves"][k]; w0 = 0.35 + 0.3 * i
        yellow(m_, w0, w0 + 0.7)
        PR.wilt(h_, m_, w0 + 0.3, w0 + 1.2, droop_deg=72, to=0.5)   # brown, blackening, collapsed limp down the stem
    T_SAG, T_G0, T_G1, T_LET = 0.35, 1.2, 2.0, 2.75    # it sags; he takes it from underneath; lifts it to his eye line; holds; lets go
    UP = -32                                          # held clearly ABOVE level, near his eye line: the lift reads
    def pitch(t):
        if t < T_SAG: return -5
        if t < T_G0: return -5 + 50 * ease((t - T_SAG) / (T_G0 - T_SAG))      # it sags far down toward him
        if t < T_G1: return 45 - (45 - UP) * ease((t - T_G0) / (T_G1 - T_G0))  # he lifts it right back up
        if t < T_LET: return UP
        u = t - T_LET; FALL = 0.32                    # it drops (gravity, ease-in), then swings limp on its stalk and stops
        if u < FALL: return UP + (74 - UP) * (u / FALL) ** 2
        w = u - FALL; return 74 - 14 * math.exp(-w / 0.35) * math.sin(w * 11) if w < 1.6 else 74
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; hz.rotation_euler = (0, math.radians(pitch(t)), to_him); hz.keyframe_insert("rotation_euler", frame=f)
    yellow(hm, T_SAG, T_G0 + 0.3)
    PR.rot(hm, T_SAG, T_LET + 0.4, to=0.55)     # dead in his hand: it browns as it drops, still a leaf, not a black rag
    side = near_hand(data, Vector((PX, PY, 0.5)))
    def under_leaf(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return hz.matrix_world @ Vector((0.17, 0, 0.0))    # his fingers UNDER the blade, mid-leaf, not brushing the tip
    reach(data, side, under_leaf, T_G0, T_LET, lead=0.4, back=0.55, elbow_out=0.4)
    US = (0.03, -2.4, 0.6)
    data.look_at((PX, PY, 0.3), 0.0, max_yaw=25, blend=0.0)  # the rot climbing out of the soil
    data.look_at((PX, PY, 0.5), T_SAG + 0.2, max_yaw=25)      # the leaf sagging
    data.look_at((PX + 0.14, PY, 0.62), T_G1 - 0.1, max_yaw=25)  # the leaf held up at his eye line: come on
    data.look_at((PX + 0.1, PY, 0.25), T_LET + 0.15, max_yaw=25)  # his eyes drop with it
    data.look_at(US, T_LET + 0.6, max_yaw=25)                  # then to us: it's gone
    T_SH = T_LET + 0.85                                        # a slow head shake to us: no
    for j, dx in enumerate((-0.35, 0.35, -0.25, 0.0)):
        data.look_at((US[0] + dx, US[1], US[2]), T_SH + 0.2 * j, max_yaw=25)
    data.idle(0.0, DUR)
    # the acting (keyed after idle): he leans in to the plant, lifts with his body, settles back as he lets go, then
    # his shoulders and head sag as the leaf lands, held to the end
    T_SLUMP = T_LET + 0.5
    data._k("spine", 0.0, rot=(0, 0, 0)); data._k("spine", T_SAG + 0.3, rot=(5, 0, 2))
    data._k("spine", T_G0, rot=(11, 0, 4)); data._k("spine", T_G1, rot=(3, 0, 3)); data._k("spine", T_LET, rot=(3, 0, 2))
    data._k("spine", T_SLUMP - 0.15, rot=(1, 0, 0)); data._k("spine", T_SLUMP + 0.35, rot=(10, 0, 0)); data._k("spine", DUR, rot=(9, 0, 0))
    data.expression("worried", 0.2, DUR)
    data._face(T_SLUMP + 0.3, brow=0.12, lid=0.3, frown=1.0); data._face(DUR, brow=0.12, lid=0.3, frown=1.0)
    data.blink(0.9); data.blink(T_G1 + 0.25)
    data.finish()
    soft_key("plant key", (-0.75, -1.4, 1.0), (PX, PY, 0.45), energy=55, size=30)
    # low and closer: the stem and leaves big on a phone, plant and Data both whole, his head clear of the top edge;
    # the camera creeps in the whole shot so the end is never a dead hold
    # take 4: the push-in is short and drifts toward the plant, so the end holds the dead plant AND his face
    C0, C1 = Vector((0.06, -1.64, 0.34)), Vector((0.03, -1.50, 0.36))
    LK0, LK1 = Vector((0.06, -0.38, 0.40)), Vector((0.02, -0.38, 0.38))
    cam = K.camera(tuple(C0), tuple(LK0), lens=26, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK0.lerp(LK1, ease(t / DUR)), (PX, PY, 0.45)))
    leaves = [o for h_, _ in pt["leaves"] for o in h_.children]
    return dict(**where, data=data, rest=1, grips=("young plant",),
                conseq=[("the rot climbs the stem", [pt["stem"], fung], T_CLIMB0, T_CLIMB1),
                        ("the leaves droop", leaves, 0.5, DUR),
                        ("the lifted leaf flops down", list(hz.children), T_LET, DUR)])


# ================================================================ SHOT 5: no banana to switch to
# shot 5's own rail: it recedes almost straight away from the lens at his right hand, so the rot comes TOWARD the
# camera and him, and the whole row, the box under its far end and Data fit one frame (no pan)
S5_YAW = 62
S5_R0 = (0.0, -0.78)
S5_DP, S5_DROT = Vector((-0.22, -0.74, 0)), 15
S5_C0, S5_LK0 = Vector((0.0, -1.95, 0.64)), Vector((0.0, -0.2, 0.40))


def shot5():
    """THE PAYOFF. The rail again, an ECUADOR banana box under its far end. The rot starts at the bunch over the box
    and comes down the row toward him; each bunch goes black on its hook, one after another. He snatches the LAST
    yellow bunch off its hook and hugs it to his chest, looking at us, the camera pushing in to him. It ends there."""
    # take 2 (judge, 63): "Data enters as a blurred head cut by the left edge that lurches into frame", "the rot runs
    # on the right and partly behind Data, the rail cut by the right edge", "the bunches drop off rather than blackening
    # on them", "the snatch happens in two frames, behind his own body", "a ghosted eye on a blink", "the bunch is small,
    # held low, pinned under one hand; its blue caps look like pins". Now: NO PAN. The rail recedes straight away from
    # the lens beside him (62 deg), the ECUADOR box under its far end; one frame holds the box, the whole row and Data
    # whole on the left from frame one, and the FOCUS racks from the box down the row with the rot to him. The bunches
    # go black ON their hooks and stay there, shivering. He winds up (hand cocked at the shoulder), snatches the last
    # one off its hook with a fast strike, yanks it to his chest and wraps both arms round its middle, squeezes, and
    # looks to us relieved as the camera pushes in. No stickers, no blinks.
    where = place("dock")
    mats = [PR.skin_mat(f"rail {k}") for k in range(N_HOOK)]
    rows = rail_row(lambda k: mats[k], sticker=False, r0=S5_R0, yaw=S5_YAW)
    R = Matrix.Rotation(math.radians(S5_YAW), 3, 'Z')
    s0 = Vector((S5_R0[0], S5_R0[1], 0))
    box = s0 + R @ Vector((RAIL_LEN + 0.15, 0.1, 0))             # past the far end, just behind it: the far bunch hangs over it
    # take 3 (judge 66): "does not open on the ECUADOR box ... small at far right", "the bunches are tiny", "the snatch
    # is motion blur, the last yellow one never singled out", "the final close crops his head". Now: ONE continuous
    # move, no cut (the cut scored 55). It opens CLOSE on the box with the far bunch over it on a long lens, then
    # travels back and pans down the row WITH the rot to a nearer medium on Data and the near bunches; a spot comes up
    # on the last yellow one and everything holds a beat on it; a slower grab; the push-in ends a little wider.
    C_OP = Vector((0.62, -1.2, 0.42))                            # the opening: just off the row's right side, facing the box
    C_MD, LK_MD = Vector((0.03, -1.6, 0.58)), Vector((-0.07, -0.6, 0.42))   # the medium: closer than take 3, the row bigger
    to_cam = C_OP - box
    PR.produce_box("ecuador box", (box.x, box.y, 0.0), yaw=math.atan2(to_cam.x, -to_cam.y))   # its printed face to the lens
    T0_, STEP, ROT_S = 0.35, 0.42, 0.45
    order = list(range(N_HOOK - 1, 0, -1))                       # from the far end toward him; the last one (k = 0) never rots
    tb_of = {k: T0_ + STEP * i for i, k in enumerate(order)}
    for k, tb in tb_of.items():
        PR.rot(mats[k], tb, tb + ROT_S, to=1.0, frm=0.1)         # it goes black ON its hook, and stays there
        PR.swing(rows[k][1], tb + ROT_S - 0.1, amp_deg=5, period=0.6, tau=0.35, nf=F(tb + ROT_S + 1.0))   # a dead shiver
    T_ARR = tb_of[1] - 0.05                  # the camera has arrived on him as the one beside the last starts to turn
    T_LAST = tb_of[1] + ROT_S                # ... it is black: ONE yellow bunch left, held a beat under its own light
    T_W = T_LAST + 0.5                       # then he cocks his hand
    T_STRIKE = T_W + 0.28; T_GRAB = T_STRIKE + 0.3; T_HUG = T_GRAB + 0.4; T_SQ = T_HUG + 0.5
    data = load_data()
    DP = S5_DP; data.place(DP.x, DP.y, S5_DROT)
    sc.frame_set(1); bpy.context.view_layer.update()
    last = rows[0]; lroot, lfing = last[2], last[3]
    sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}; mid = (sh["L"] + sh["R"]) / 2
    fwd = data.forward(); lat = Vector((math.cos(math.radians(S5_DROT)), math.sin(math.radians(S5_DROT)), 0))
    M0 = lroot.matrix_world.copy()
    c0 = sum((fo.matrix_world.translation for fo in lfing), Vector()) / len(lfing)    # the bunch's MIDDLE, not its stem
    from mathutils import Quaternion
    q0 = M0.to_quaternion(); off_l = q0.inverted() @ (c0 - M0.translation)
    q1 = Quaternion((0, 0, 1), math.radians(14)) @ Quaternion((0, 1, 0), math.radians(-90)) @ Quaternion((1, 0, 0), math.radians(-12))
    chest = mid + fwd * 0.16 + Vector((0, 0, -0.04))             # high on his chest, under the chin: big in the close-up
    u_of = lambda t: ease((t - T_GRAB) / (T_HUG - T_GRAB))
    sq = lambda t: ease((t - T_SQ) / 0.3)                         # the protective squeeze
    def center(t):
        u = u_of(t)
        return c0.lerp(chest, u) + Vector((0, 0, 0.06 * math.sin(math.pi * u))) - fwd * 0.015 * sq(t)
    lroot.parent = None; lroot.matrix_world = M0; lroot.rotation_mode = 'QUATERNION'
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; q = q0.slerp(q1, u_of(t))
        lroot.rotation_quaternion = q; lroot.keyframe_insert("rotation_quaternion", frame=f)
        lroot.location = center(t) - q @ off_l; lroot.keyframe_insert("location", frame=f)
    grab = near_hand(data, c0); hold = "L" if grab == "R" else "R"
    sx = {s_: (1 if (sh[s_] - mid).dot(lat) > 0 else -1) for s_ in "LR"}
    hug_off = lambda s_, t: lat * sx[s_] * (0.07 - 0.015 * sq(t)) + fwd * 0.02    # both arms round its middle
    wind = sh[grab] + lat * sx[grab] * 0.09 - fwd * 0.05 + Vector((0, 0, 0.04))   # the wind-up: hand cocked up by his shoulder
    g_off = (sh[grab] - c0).normalized() * 0.05                                   # the grab: on the bunch's near side
    def grab_pt(t):
        if t < T_STRIKE: return wind
        if t < T_GRAB: return wind.lerp(c0 + g_off, ease((t - T_STRIKE) / (T_GRAB - T_STRIKE)))
        return center(t) + g_off.lerp(hug_off(grab, t), u_of(t))
    reach(data, grab, grab_pt, T_W, DUR, lead=0.3, elbow_out=0.45)
    reach(data, hold, lambda t: center(t) + hug_off(hold, t), T_GRAB + 0.1, DUR, lead=0.35, elbow_out=0.5)
    C1, LK1 = Vector((DP.x + 0.06, DP.y - 0.80, 0.60)), Vector((DP.x + 0.04, DP.y, 0.48))   # a little wider: head clear
    US = tuple(C1)
    # his eyes ride the rot down the row toward him, land on the last yellow one, follow it to his chest, then to us
    data.look_at(rows[N_HOOK - 1][0], 0.0, max_yaw=30, blend=0.0)
    for k in order[1:]:
        data.look_at(rows[k][0], tb_of[k] + 0.2, max_yaw=30)
    data.look_at(c0, T_LAST - 0.15, max_yaw=30)                  # the last yellow one: he stares at it
    data.look_at(chest + Vector((0, 0, 0.03)), T_HUG + 0.05, max_yaw=30)
    data.look_at(US, T_HUG + 0.6, max_yaw=30)
    data.idle(0.0, DUR)
    data.expression("worried", 0.2, T_LAST)
    data.expression("alarmed", T_LAST, T_HUG + 0.15)
    data.expression("happy", T_HUG + 0.45)        # relief, held to the end (no end time: no fade to neutral on the payoff)
    data.finish()                                 # no blinks: a closing lid ghosted inside the lens (take 1, frame 22)
    soft_key("rail key", (0.9, -1.5, 1.1), (0.25, -0.35, 0.42), energy=40, size=36)
    soft_key("box key", (0.9, -0.9, 0.8), (box.x, box.y, 0.1), energy=22, size=20)
    soft_key("hug key", (-0.5, -1.6, 0.9), tuple(chest), energy=18, size=18)
    lk = soft_key("last key", (0.35, -1.45, 1.0), tuple(c0), energy=0, size=13)    # the spot on the LAST yellow bunch
    lk.data.energy = 0; lk.data.keyframe_insert("energy", frame=F(T_LAST - 0.35))
    lk.data.energy = 30; lk.data.keyframe_insert("energy", frame=F(T_LAST + 0.05))
    # opens CLOSE on the box on a long lens, travels back down the row with the rot to the medium, holds on the last
    # one, then pushes in on the hug
    LK_OP = box + Vector((0, 0, 0.27))                           # the box and the far bunch hanging over it
    def path(t):
        if t < T_ARR:
            a = ease(t / T_ARR); return C_OP.lerp(C_MD, a), LK_OP.lerp(LK_MD, a)
        b = 0.1 * ease((t - T_ARR) / (T_GRAB - T_ARR)) + 0.9 * ease((t - T_GRAB) / (DUR - 0.2 - T_GRAB))
        return C_MD.lerp(C1, b), LK_MD.lerp(LK1, b)
    foc_end = Vector((DP.x + 0.02, DP.y - 0.12, 0.5))
    fk = [(0.0, box + Vector((0, 0, 0.12))), (0.5, rows[N_HOOK - 1][0] - Vector((0, 0, 0.1)))]
    fk += [(tb_of[k] + 0.2, rows[k][0] - Vector((0, 0, 0.1))) for k in order[1:]] + [(T_LAST, c0), (T_W + 0.3, foc_end)]
    def focus(t):
        for (ta, pa), (tz, pz) in zip(fk, fk[1:]):
            if t < tz: return pa.lerp(pz, ease((t - ta) / (tz - ta)))
        return foc_end
    cam = K.camera(tuple(C_OP), tuple(LK_OP), lens=50, fstop=4.0)
    camera_path(cam, lambda t: (*path(t), focus(t)))
    cam.data.lens = 50; cam.data.keyframe_insert("lens", frame=1)
    cam.data.lens = 26; cam.data.keyframe_insert("lens", frame=F(T_ARR))
    cam.data.lens = 26; cam.data.keyframe_insert("lens", frame=F(T_GRAB))
    cam.data.lens = 28; cam.data.keyframe_insert("lens", frame=F(DUR - 0.2))
    fallen = [r[2] for r in rows[1:]]
    return dict(**where, data=data, rest=1, grips=("rail bunch 0",), cutaway=(0.0, T_ARR * 0.8),
                conseq=[("the bunches go black one after another, toward him", lambda: meshes(fallen), T0_, T_GRAB),
                        ("he holds the last yellow bunch", lambda: meshes([lroot]), T_HUG, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


