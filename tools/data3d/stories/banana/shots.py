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
    lean = [(0.0, 0, 0), (T_REC, 0, 0), (T_REC + 0.12, 30, 21), (T_REC + 0.45, 21, 14),
            (T_DROP2 + 0.12, 18, 12), (T_FL2 + 0.13, 27, 19), (T_FL2 + 0.45, 21, 14),
            (T_DROP3 + 0.1, 20, 13), (T_DROP3 + 0.25, 26, 18), (T_DROP3 + 0.55, 22, 15), (DUR, 22, 15)]
    for t_, b_, s_ in lean:
        data._k("spine", t_, rot=(BK * b_, 0, SD * s_)); data._k("chest", t_, rot=(BK * b_ * 0.45, 0, SD * s_ * 0.45))
    REACH = 0.995 * (data.U + data.Fo)
    out = lambda t: ease((t - T_REC) / 0.26)
    # the fan spread flat to the lens so every finger is its own shape (fingers at the lens fanned into one blob)
    tilt = lambda t: Vector((math.radians(90), math.radians(-38 - 10 * out(t)), 0))
    # judge 48: "hands are round blobs crossed over the chest ... next to the fruit, not holding it": one hand closes on
    # the CROWN (the stem end), the other cups the fingers from behind, and each hand takes the point on ITS OWN side
    from mathutils import Euler
    S_LO = "L" if sh0["L"].x < sh0["R"].x else "R"
    def hand_off(s_, c, t):
        R_ = Euler(tuple(tilt(t)), 'XYZ').to_matrix()
        a_ = c + R_ @ Vector((-0.03, 0.0, -0.012)); b_ = c + R_ @ Vector((0.09, 0.0, -0.035))
        lo_, hi_ = (a_, b_) if a_.x <= b_.x else (b_, a_)
        return lo_ if s_ == S_LO else hi_
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; sc.frame_set(f); bpy.context.view_layer.update()
        sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
        c = P0.lerp(P1, out(t))
        shake = min(1.0, max(0.0, (t - T_REC - 0.25) / 0.3))           # it trembles in his outstretched hands
        c = c + Vector((0.005 * math.sin(2 * math.pi * 9 * t), 0, 0.005 * math.sin(2 * math.pi * 11 * t + 1))) * shake
        for _ in range(10):                                            # held at his reach, never past it
            worst = None
            for s_ in "LR":
                d_ = hand_off(s_, c, t) - sh[s_]
                if d_.length > REACH and (worst is None or d_.length - REACH > worst[0]): worst = (d_.length - REACH, d_)
            if worst is None: break
            c = c - worst[1].normalized() * (worst[0] + 1e-4)
        hero.location = c; hero.keyframe_insert("location", frame=f)
        hero.rotation_euler = tuple(tilt(t) + Vector((0.035 * math.sin(2 * math.pi * 7 * t), 0, 0)) * shake)
        hero.keyframe_insert("rotation_euler", frame=f)
        for s_ in "LR":
            data._arm_ik(s_, hand_off(s_, c, t), t, 0.4)
    # the rot: a clean bright bunch on frame one, patches spreading all through the shot (it never stops)
    # judge 48: "the rot runs backwards" (black at 2.4 s, spotted again after): hm.copy() SHARED the bunch's action, so
    # every fallen finger's keys were written into the bunch's own curve. Now ONE forward-only curve that ends fully
    # black, and every copy gets its own action.
    ROT = ((0.0, 0.1), (0.15, 0.12), (T_DROP, 0.40), (T_DROP2, 0.47), (T_DROP3, 0.56), (DUR, 0.64))
    def rot_at(t):
        for (ta, va), (tb, vb) in zip(ROT, ROT[1:]):
            if t <= tb: return va + (vb - va) * max(0.0, t - ta) / max(1e-6, tb - ta)
        return ROT[-1][1]
    rv = PR.rot_node(hm)
    for t_, v_ in ROT:
        rv.default_value = v_; rv.keyframe_insert("default_value", frame=F(t_))
    # judge 62: "the dropped banana lands as a large dark log ... a sausage": a finger that has left the bunch stops
    # rotting where it was, so it lies on the table a spotted YELLOW banana, not a black slug (own material per object)
    def own_rot(fo, t_hold):
        try:
            m_ = hm.copy()
            if m_.node_tree.animation_data: m_.node_tree.animation_data_clear()
            rv_ = PR.rot_node(m_)
            hold = rot_at(t_hold)
            for t_, v_ in [k_ for k_ in ROT if k_[0] < t_hold - 0.02] + [(t_hold, hold), (DUR, hold + 0.04)]:
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
    # only two fingers go: a third appearing on the table read as a pile that "came from nowhere" (judge 48)
    f2 = fingers[3]
    bake(f2, T_DROP2)
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
    data.look_at(bunch_at(T_DROP3) + Vector((0, 0, 0.05)), T_DROP3 + 0.05, max_yaw=30)      # it has gone all black
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
    # judge 48: "never seen dropping ... only after it has landed": it pops UP off the bunch first, so the fall lasts
    # about half a second (several sampled frames mid-air) and lands with a bounce. And "twice the size of the bananas
    # still in the bunch" (it lies broadside, nearer the lens): it eases to the bunch's apparent size as it falls.
    own_rot(fingers[0], T_DROP); own_rot(f2, T_DROP2)
    drop(fingers[0], T_DROP, TABLE_H + 0.034, kick=(0.3, -0.15, 1.7), spin=(2, 0.5, 3), bounce=0.45)
    drop(f2, T_DROP2, TABLE_H + 0.034, kick=(-0.1, -0.05, 1.5), spin=(-2, 0.4, 3), bounce=0.45)
    for fo, t_go in ((fingers[0], T_DROP), (f2, T_DROP2)):
        for t_, k_ in ((0.0, 1.0), (t_go, 1.0), (t_go + 0.4, 0.78), (DUR, 0.78)):
            fo.scale = (k_, k_, k_); fo.keyframe_insert("scale", frame=F(t_))
    soft_key("bunch key", (0.5, -1.0, 0.9), tuple(P0), energy=24, size=26)
    # a medium close (30 mm) that JOLTS in 5 cm with his recoil (the camera reacts with him), then holds
    # judge 48: "frame a little tighter ... the large empty counter in the bottom third does nothing"
    C0, LK = Vector((0.05, -1.0, 0.68)), Vector((mid.x + 0.03, -0.1, 0.55))
    cam = K.camera(tuple(C0), tuple(LK), lens=34, fstop=3.2)
    camera_path(cam, lambda t: (C0 + Vector((0, 0.05 * ease((t - T_REC) / 0.2), 0)), LK, P0))
    rest_f = [fo for k, fo in enumerate(fingers) if k not in (0, 3)]
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
    """COPIES OF ONE PLANT: WHAT KILLS ONE CAN KILL THEM ALL. A row of identical young banana plants in identical pots
    stands like dominoes down the warehouse floor, running away to the right; Data at its left end, turned to us, gives
    the first one a straight-arm shove and the whole row goes down, each one knocking over the next, all the way. He
    watches it run away from him, then turns to us, alarmed: one push, every one of them."""
    # 2026-11-13 caaleb, of the banana short's first five shots: "All those were just varying shots of bananas getting
    # browner." This beat's idea is DOMINOES: the clone fact as a chain reaction, nothing turning brown.
    where = place("warehouse")
    # the row is a CURVE, the way domino runs are laid: it leaves him running across the frame (so the first falls are
    # seen side-on, one knocking the next) and bends away into depth (so the whole run fits a phone frame). Judge,
    # take 1 (44): a straight row away from the lens "goes down as one clump" and "reads as ONE big fallen plant".
    N, SP, R, H0 = 7, 0.28, 1e4, math.radians(50)
    D = Vector((math.cos(H0), math.sin(H0), 0))
    DP, DROT = Vector((-0.38, -0.85, 0)), 16
    POT_R, POT_H, PH = 0.07, 0.13, 0.3
    B0 = DP + Vector((0.27, 0.06, 0))                  # the first pot's centre, an arm's length from him
    CTR = B0 + R * Vector((-math.sin(H0), math.cos(H0), 0))
    head = lambda k: H0 + SP * k / R
    P = lambda k: CTR + R * Vector((math.sin(head(k)), -math.cos(head(k)), 0))
    Tn = lambda k: Vector((math.cos(head(k)), math.sin(head(k)), 0))
    T_PUSH, FALL, STEP = 1.3, 0.6, 0.6              # the push lands; one plant's fall; the next starts when it is hit
    LEAN = 62                                         # each comes to rest leaning on the one ahead; the last lies flat
    T_END = T_PUSH + STEP * (N - 1) + FALL + 0.25
    T_WHOA = min(T_END - 0.3, DUR - 1.0)   # the chain fills the beat; his reaction lands on the last plant
    terra = K.mat("pot clay", "#B4643E", rough=0.8); rim = K.mat("pot rim", "#A35A37", rough=0.8)
    soil = K.mat("pot soil", "#3A2A1E", rough=0.95)
    tag_m = K.mat("plant tag", "#F2F0EA", rough=0.5); band_m = K.mat("plant tag band", "#1F5FA8", rough=0.5)

    def tilt_at(k, t):
        """degrees from upright of plant k at time t: still, then a gravity fall (ease-in), a small bounce, at rest"""
        t0 = T_PUSH + STEP * k; u = t - t0
        end = 86 if k == N - 1 else LEAN + (6 if k % 2 else 0)
        if u <= 0: return 0.0
        if u < FALL: return end * (u / FALL) ** 2
        w = u - FALL
        return end - 6 * math.exp(-w / 0.12) * abs(math.sin(w * 18)) if w < 0.6 else end

    pivots, plants = [], []
    for k in range(N):
        c = P(k); YAW = math.degrees(head(k)) + (11 if k % 2 else -11) * (k > 0)   # each falls a little off line: splayed, separate pots (judge: "one orange tube")
        pv = K.empty(f"domino {k} pivot", tuple(c + Vector((math.cos(math.radians(YAW)), math.sin(math.radians(YAW)), 0)) * POT_R)); pv.rotation_euler = (0, 0, math.radians(YAW))
        K.cyl(f"domino {k} pot", (c.x, c.y, POT_H / 2), POT_R, POT_H, terra, v=28, bev=0.006, parent=pv)
        K.cyl(f"domino {k} pot rim", (c.x, c.y, POT_H - 0.012), POT_R + 0.008, 0.024, rim, v=28, bev=0.004, parent=pv)
        K.cyl(f"domino {k} soil", (c.x, c.y, POT_H - 0.006), POT_R - 0.004, 0.012, soil, v=28, bev=0.0, parent=pv)
        pt = PR.plant(f"domino {k} plant", (c.x, c.y, POT_H - 0.01), height=PH, seed=8,
                      angles=(YAW + 65, YAW + 115, YAW + 245, YAW + 295), parent=pv)   # four leaves to the sides: fallen, each plant is its own shape
        for h_, _ in pt["leaves"]: h_.scale = (1.15, 1.15, 1.15)   # a banana pup: a short stout stem, broad paddles
        # the SAME white tag in every pot, blue band and all: the clones wear one label
        tag = K.box(f"domino {k} tag", (c.x - Tn(k).y * 0.035, c.y + Tn(k).x * 0.035 - 0.03, POT_H + 0.035), (0.05, 0.006, 0.065), tag_m, bev=0.003, parent=pv)
        K.box(f"domino {k} tag band", (c.x - Tn(k).y * 0.035, c.y + Tn(k).x * 0.035 - 0.0335, POT_H + 0.05), (0.05, 0.002, 0.018), band_m, bev=0.0, parent=pv)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; pv.rotation_euler = (0, math.radians(tilt_at(k, t)), math.radians(YAW))
            pv.keyframe_insert("rotation_euler", frame=f)
        pivots.append(pv); plants.append(pt)
    data = load_data()
    data.place(DP.x, DP.y, DROT)
    sc.frame_set(1); bpy.context.view_layer.update()

    def head_with(rx):
        data.pb["spine"].rotation_euler = (math.radians(rx), 0, 0); bpy.context.view_layer.update()
        return (data.arm.matrix_world @ data.pb["head"].head).copy()
    h0 = head_with(0); BK = -1 if (head_with(-10) - h0).y > 0 else 1
    data.pb["spine"].rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
    sc.frame_set(1); bpy.context.view_layer.update()
    stem0 = plants[0]["stem"]
    side = near_hand(data, stem0.matrix_world.translation)
    REACH = 0.995 * (data.U + data.Fo) * data.arm.scale.x
    HZ = POT_H + PH * 0.42                           # where his hand meets the first stem

    def on_stem(t):                                  # the near side of the first stem, riding it as it starts to go
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        M = pivots[0].matrix_world
        return M @ (pivots[0].matrix_world.inverted() @ Vector((B0.x, B0.y, HZ)) * 0 + Vector((-POT_R - 0.035, 0, HZ)))

    def out_dir(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        sh_ = acts._shoulder(data, side); fw = data.forward()
        o_ = Vector((-fw.y, fw.x, 0)); o_ = o_ if o_.dot(sh_ - data.pos()) > 0 else -o_
        return sh_, fw, o_.normalized()

    def rest(t):
        sh_, fw, o_ = out_dir(t)
        return sh_ + o_ * 0.09 + fw * 0.05 + Vector((0, 0, -0.85 * REACH))
    # a wind-up, the strike on the stem, a beat riding it as it goes, and the hand back (judge: "no wind-up and no contact")
    WAY = [(0.0, 'r'), (T_PUSH - 0.7, 'r'), (T_PUSH - 0.4, 'w'), (T_PUSH - 0.12, 'w'), (T_PUSH - 0.01, 's'), (T_PUSH + 0.25, 's'), (T_PUSH + 0.6, 'r')]

    def hand(t):
        pt_ = lambda w: on_stem(t) if w == 's' else (on_stem(t) - Tn(0) * 0.2 + Vector((0, 0, 0.06)) if w == 'w' else rest(t))
        for (ta, wa), (tz, wz) in zip(WAY, WAY[1:]):
            if t <= tz:
                if wa == wz: return pt_(wa)
                u = ease((t - ta) / max(1e-6, tz - ta))
                return pt_(wa).lerp(pt_(wz), u) + out_dir(t)[2] * 0.05 * math.sin(math.pi * u)
        return rest(t)
    reach(data, side, hand, T_PUSH - 0.7, WAY[-1][0], lead=0.3, back=0.35, elbow_out=0.45)   # the arm hangs until the wind-up (judge: "his arm is already held out")
    C0, C1 = Vector((-0.3, -2.33, 0.68)), Vector((-0.29, -2.27, 0.67))
    LK = Vector((-0.08, -0.35, 0.36))
    US = tuple(C1)
    mid = P(N // 2)
    data.look_at(B0 + Vector((0, 0, HZ)), 0.0, max_yaw=18, blend=0.0)
    data.look_at(US, 0.35, max_yaw=18)                                     # to us: watch this
    data.look_at(B0 + Vector((0, 0, HZ)), T_PUSH - 0.6, max_yaw=22)                # he looks at what he is about to push
    for k_ in range(1, N, 2):                                                 # his eyes ride the fall away, plant by plant
        data.look_at(P(k_) + Vector((0, 0, 0.15)), T_PUSH + STEP * k_, max_yaw=22)
    data.look_at(US, T_WHOA + 0.05, max_yaw=18)                           # to us: all of them
    data.idle(0.0, DUR)
    data._k("spine", 0.0, rot=(0, 0, 0)); data._k("spine", T_PUSH - 0.45, rot=(0, 0, 0))
    data._k("spine", T_PUSH - 0.15, rot=(BK * 6, 0, 0))                    # the wind-up: he rocks back
    data._k("spine", T_PUSH + 0.08, rot=(-BK * 11, 0, 0))                  # and throws his weight into the shove
    data._k("spine", T_PUSH + 0.7, rot=(0, 0, 0)); data._k("spine", T_WHOA - 0.05, rot=(0, 0, 0))
    data._k("spine", T_WHOA + 0.18, rot=(BK * 12, 0, 0)); data._k("spine", T_WHOA + 0.5, rot=(BK * 8, 0, 0))
    data._k("spine", DUR, rot=(BK * 9, 0, 0))
    data.act("whoa", T_WHOA, dur=0.22, hold=max(0.6, DUR - T_WHOA - 0.3))
    data.expression("happy", 0.05, T_PUSH + 0.5)
    data.expression("surprised", T_PUSH + 0.6, T_PUSH + STEP * 4)
    data.expression("alarmed", T_PUSH + STEP * 4 + 0.05, blend=0.12)
    AL = dict(data.EXPRESSIONS["alarmed"]); AL["frown"] = 1.0
    data._face(T_WHOA, **AL); data._face(DUR, **AL)
    data.blink(0.5)
    data.finish()
    soft_key("row key", (0.8, -1.6, 1.1), tuple(mid + Vector((0, 0, 0.3))), energy=45, size=36)
    cam = K.camera(tuple(C0), tuple(LK), lens=24, fstop=5.6)
    # a CRANE UP as the run goes down: from his eye line (the row standing, side-on) to above the floor, so the fallen
    # row lies out as six separate pots and stems in a line, not one heap (judge, take 1: "one big frond heap")
    C2, LK2 = C1, LK + Vector((0.05, 0.15, -0.03))   # the end drifts toward the far end of the fallen row
    TC0, TC1 = T_PUSH + STEP * 2.5, min(DUR - 0.6, T_END + 0.9)
    crane = lambda t: ease(min(1.0, max(0.0, (t - TC0) / (TC1 - TC0))))
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)).lerp(C2, crane(t)), LK.lerp(LK2, crane(t)), mid))
    return dict(**where, data=data, rest=1, grips=("domino 0",),
                conseq=[("the row falls like dominoes", lambda: meshes(pivots), T_PUSH, T_END)])


# ==== banana track kit (shots 3 and 5)
# THE SWITCH (caaleb 2026-11-13: the banana short's shots were "all just varying shots of bananas getting browner"). The
# 1950s beat and the payoff are one idea told twice: a little banana railway forks at a set of points worked by a
# big switch lever (the master-switch lever of the checkout short, which caaleb called "the best Data visual in the
# whole show"). In 1950 he hauls it and a fresh CAVENDISH cart rolls in on the new branch; at the Ecuador dock he
# hauls the SAME lever, the points move, and there is no second track. Same lever, same spot, same lens: a callback.
TK_G = 0.13                        # the gauge
TK_SW = Vector((-0.06, 0.45, 0))    # the points: the stem runs back from here, the two branches come toward the lens
TK_LX = -0.2                      # the LEFT branch (the old one) bends out to here and runs on to the front
TK_RX = 0.1                       # the RIGHT branch (the new one) bends out to here
TK_END = -0.42                     # both branches end at buffer stops here, at the front
TK_P = Vector((0.46, 0.42, 0))      # where Data stands to haul the lever: BESIDE and a little behind the points, so
                                   # nothing of the fork, the branches or the carts is ever behind him (judge: the cart
                                   # "rolls in behind Data ... half-hidden by his body")
TK_CAM = Vector((0.12, -1.6, 1.1))    # the lever faces this lens (the medium): high, so the fork reads as a Y on the ground


def tk_clear(r=1.4):
    """take the ground dressing (grass patches) off the set: the clipping check reads a flat patch as a solid"""
    for o in list(bpy.data.objects):
        if o.name.startswith("grass patch") and (o.location.xy - TK_SW.xy).length < r + max(o.scale.x, o.scale.y):
            bpy.data.objects.remove(o)


def tk_mats():
    return dict(steel=K.mat("tk rail", "#77716A", rough=0.38, metal=0.75), tie=K.mat("tk tie", "#5C4632", rough=0.9),
                blade=K.mat("tk blade", "#F0C232", rough=0.35, metal=0.2))   # painted points: you can SEE them throw)


def tk_line(pts, n=40):
    """dense points along a polyline given as Vectors"""
    out = []
    for a, b in zip(pts, pts[1:]):
        k = max(1, int((b - a).length / 0.03))
        out += [a.lerp(b, i / k) for i in range(k)]
    return out + [pts[-1]]


def tk_stem(y_back=2.8):
    return [Vector((TK_SW.x, y_back, 0)), TK_SW.copy()]


def _tk_s(x_to):
    P0 = TK_SW; P3 = Vector((x_to, TK_SW.y - 0.62, 0)); P1 = P0 + Vector((0, -0.31, 0)); P2 = P3 + Vector((0, 0.31, 0))
    pts = [((1 - u) ** 3) * P0 + 3 * ((1 - u) ** 2) * u * P1 + 3 * (1 - u) * u * u * P2 + (u ** 3) * P3 for u in [i / 14 for i in range(15)]]
    return pts + [Vector((x_to, TK_END, 0))]


def tk_right():
    """the new branch: an S out to TK_RX, then straight to the front"""
    return _tk_s(TK_RX)


def tk_left():
    """the old branch: an S out to TK_LX, then straight to the front"""
    return _tk_s(TK_LX)


def tk_buffer(name, x, M):
    """a buffer stop at a branch's end: two posts and a striped beam"""
    hz = K.mat("tk buffer", "#D8B43A", rough=0.55)
    for sg in (-1, 1): K.box(f"{name} post", (x + sg * TK_G / 2, TK_END - 0.03, 0.06), (0.03, 0.03, 0.12), M["tie"], bev=0.004)
    K.box(f"{name} beam", (x, TK_END - 0.05, 0.1), (TK_G + 0.08, 0.035, 0.045), hz, bev=0.004)


def tk_track(name, pts, M, ties=True, skip_rails_before=0.0):
    """two rails on wooden ties along a polyline (Vectors on the ground)"""
    s = 0.0; acc = 0.0
    for a, b in zip(pts, pts[1:]):
        d = b - a; L = d.length
        if L < 1e-6: continue
        yaw = math.atan2(d.y, d.x); n = Vector((-d.y, d.x, 0)).normalized()
        if s + L > skip_rails_before:
            for sg in (-1, 1):
                c = (a + b) / 2 + n * sg * TK_G / 2
                K.box(f"{name} rail", (c.x, c.y, 0.022), (L + 0.006, 0.013, 0.018), M["steel"], bev=0.002).rotation_euler = (0, 0, yaw)
        if ties:
            while acc <= s + L:
                p = a + d * ((acc - s) / L)
                K.box(f"{name} tie", (p.x, p.y, 0.007), (0.034, TK_G + 0.1, 0.014), M["tie"], bev=0.002).rotation_euler = (0, 0, yaw)
                acc += 0.095
        s += L


def tk_points(M, t_of, post):
    """the two switch blades at the fork: they pivot on their heels (toward the lens) and their toes swing across as
    the lever goes over; a red throw rod runs from the lever post's foot to the toes and slides with them. t_of(t) ->
    0 (set for the LEFT branch) .. 1 (set for the RIGHT). Returns (blade pivots, rod)."""
    piv = []; LB = 0.34
    for sg in (-1, 1):
        heel = TK_SW + Vector((sg * TK_G / 2, -LB, 0))
        e = K.empty("tk blade pivot", tuple(heel))
        K.box("tk blade", (heel.x, heel.y + LB / 2, 0.028), (0.017, LB, 0.022), M["blade"], bev=0.002, parent=e)
        piv.append(e)
    toe = TK_SW + Vector((0, -0.04, 0)); foot = Vector((post.x, toe.y, 0)); d = toe - foot   # straight across, in front of his feet
    rod = K.empty("tk rod pivot", tuple(foot))
    K.box("tk throw rod", (foot.x + d.x / 2, foot.y + d.y / 2, 0.032), (d.length, 0.02, 0.02), K.mat("tk rod", "#C6392B", rough=0.4), bev=0.003, parent=rod).rotation_euler = (0, 0, math.atan2(d.y, d.x))
    dn = d.normalized()
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = t_of(t)
        for e in piv:
            e.rotation_euler = (0, 0, math.radians(-6.5) * (1 - u) + math.radians(0) * u); e.keyframe_insert("rotation_euler", frame=f)
        rod.location = tuple(foot + dn * 0.05 * u); rod.keyframe_insert("location", frame=f)
    return piv, rod


def tk_cart(name, word, fruit, M, seed=70, year=""):
    """a little flat railway cart with an open fruit crate on it, the word stencilled big on its front. Its root sits
    on the track centre at rail height, facing -Y (the crate's stencil to the lens when it runs toward us)."""
    root = K.empty(name, (0, 0, 0))
    wood = K.mat("tk cart", "#4B5056", rough=0.55, metal=0.4)
    K.box(f"{name} bed", (0, 0, 0.095), (TK_G + 0.13, 0.36, 0.03), wood, bev=0.004, parent=root)
    wm = K.mat("tk wheel", "#2B2B2E", rough=0.4, metal=0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.cyl(f"{name} wheel", (sx * TK_G / 2, sy * 0.12, 0.068), 0.04, 0.018, wm, rot=(0, math.radians(90), 0), v=20, parent=root)
    cr = PR.crate(f"{name} crate", (0, 0, 0.11), w=0.25, d=0.3, h=0.13, stencil=word, year=year, parent=root)   # a low crate: the fruit heaped over its rim
    cr["lid"].hide_render = True
    for c in cr["lid"].children: c.hide_render = True
    for nm_ in (f"{name} crate stencil", f"{name} crate year"):
        o_ = bpy.data.objects.get(nm_)
        if o_: o_.scale = (1.0, 1.0, 1.0)          # the whole word ON the slats (judge: "GROS MICH", cut by its own crate)
    ink = bpy.data.materials.get("crate ink")
    for sg in (-1, 1):                               # and down both sides: it reads whichever way the cart is turned
        K.text(f"{name} crate side", word, (sg * (0.125 + 0.008), 0, 0.11 + 0.13 * 0.6), 0.04, (math.radians(90), 0, math.radians(90 * sg)), ink, extrude=0.0006, parent=root)
    fingers = []
    for k, (dx, dy, yaw) in enumerate(((-0.055, 0.04, 0.4), (0.055, 0.02, 2.7), (0.0, 0.08, -0.3), (0.0, -0.01, 1.6))):
        r_, fs = PR.bunch(f"{name} bunch {k}", (dx, dy, cr["inner_z"] + 0.045 + (0.05 if k == 3 else 0.0)), fruit, n=5, seed=seed + k, L=0.16, spread=0.7, parent=root)
        r_.rotation_euler = (0, 0, yaw); fingers += fs
    return root, fingers


def tk_run(root, pts, s_of, t0=0.0, t1=None):
    """key a cart along a polyline: s_of(t) = the distance travelled; it faces along its travel"""
    seg, cum = [], [0.0]
    for a, b in zip(pts, pts[1:]):
        seg.append((a, b)); cum.append(cum[-1] + (b - a).length)
    def at(s):
        s = max(0.0, min(cum[-1] - 1e-6, s))
        for i, (a, b) in enumerate(seg):
            if s <= cum[i + 1]:
                u = (s - cum[i]) / max(1e-9, cum[i + 1] - cum[i]); d = (b - a).normalized()
                return a.lerp(b, u), math.atan2(d.y, d.x)
        return seg[-1][1], 0.0
    for f in range(F(t0), F(t1 if t1 is not None else DUR) + 1):
        t = (f - 1) / FPS; p, yaw = at(s_of(t))
        root.location = (p.x, p.y, 0.0); root.rotation_euler = (0, 0, yaw + math.radians(90)); root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
    return cum[-1]


def tk_lever(data, T_GRIP, T_PULL0, T_PULL1, T_LET, P=None, CA=None):
    """THE SWITCH LEVER (the checkout short's master switch): a short post beside him, its lever swinging ACROSS the
    frame in one big arc. He takes it in both hands at T_GRIP, eases it BACK (the wind-up), hauls it down hard over
    T_PULL0..T_PULL1 leaning into it, it bounces on its stop, and he lets go at T_LET. Both hands are on the ball
    every frame from T_GRIP to T_LET. Returns (progress(t): 0 up .. 1 down, the lever pivot)."""
    P = P or TK_P; CA = CA or TK_CAM
    to_cam = Vector((CA.x - P.x, CA.y - P.y, 0)).normalized()
    right = Vector((-to_cam.y, to_cam.x, 0))
    pdir = -right                      # the post on his screen-LEFT, between him and the stem: the frame ends at his shoulder, not mid-post
    post_c = P + pdir * 0.33
    ped = K.mat("switch body", "#3A3E44", rough=0.45); red = K.mat("lever knob", "#C6392B", rough=0.35)
    steel = K.mat("lever steel", "#B3B7BB", rough=0.3, metal=0.9); hz = K.mat("hazard", "#E2B33C", rough=0.5)
    yaw_post = math.atan2(-to_cam.x, to_cam.y)
    PH_ = 0.44
    for nm, z, sz, m_ in (("switch post", PH_ / 2, (0.15, 0.12, PH_), ped), ("switch band", PH_ - 0.05, (0.155, 0.125, 0.035), hz),
                          ("switch foot", 0.015, (0.15, 0.2, 0.03), ped), ("switch cap", PH_ + 0.01, (0.13, 0.14, 0.02), ped)):   # a slim post: it never crowds him or the frame
        K.box(nm, (post_c.x, post_c.y, z), sz, m_, bev=0.008).rotation_euler = (0, 0, yaw_post)
    piv = post_c + to_cam * 0.07 + Vector((0, 0, PH_ - 0.1))
    arm = K.empty("lever pivot", tuple(piv))
    LL = 0.25
    K.cyl("lever hub", tuple(piv), 0.035, 0.03, steel, rot=Matrix.Rotation(math.radians(90), 3, Vector((to_cam.y, -to_cam.x, 0)).cross(Vector((0, 0, 1)))).to_euler(), v=24, parent=arm)
    K.cyl("lever rod", (piv.x, piv.y, piv.z + LL / 2), 0.018, LL, steel, v=16, parent=arm)
    K.sph("lever ball", (piv.x, piv.y, piv.z + LL + 0.025), 0.042, red, parent=arm)
    ax = to_cam.copy()
    A0, A1, AW = math.radians(4), math.radians(135), math.radians(-18)
    sgn = 1 if (Matrix.Rotation(0.3, 3, ax) @ Vector((0, 0, 1))).dot(-pdir) > 0 else -1   # it comes over toward him
    def lever_a(t):
        if t < T_GRIP + 0.1: return A0
        if t < T_PULL0: return lerp(A0, AW, ease((t - T_GRIP - 0.1) / max(1e-3, T_PULL0 - T_GRIP - 0.1)))
        u = min(1.0, (t - T_PULL0) / (T_PULL1 - T_PULL0)); a = lerp(AW, A1, u * u * (3 - 2 * u))
        if t > T_PULL1: a = A1 - math.radians(9) * math.exp(-7 * (t - T_PULL1)) * abs(math.sin(14 * (t - T_PULL1)))
        return a
    for f in range(1, NF + 1):
        t = (f - 1) / FPS
        arm.rotation_euler = Matrix.Rotation(sgn * lever_a(t), 3, ax).to_euler(); arm.keyframe_insert("rotation_euler", frame=f)
    def grip_pt(t, k):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return arm.matrix_world @ Vector((0, 0, LL - (0.0 if k == 0 else 0.065))) + to_cam * 0.025
    sc.frame_set(F(T_GRIP)); bpy.context.view_layer.update()
    LEAN = 6
    def spine_lean(t):
        u = ease((t - T_PULL0) / (T_PULL1 - T_PULL0)); return LEAN * (1 - u) - 4 * math.sin(math.pi * u)
    sh0 = acts._shoulder(data, "L"); data._k('spine', T_GRIP, rot=(0, 0, 10)); sc.frame_set(F(T_GRIP)); bpy.context.view_layer.update()
    lean_sgn = 1 if (acts._shoulder(data, "L") - sh0).dot(pdir) > 0 else -1
    data._k('spine', 0.0, rot=(0, 0, 0)); data._k('spine', T_GRIP, rot=(0, 0, 0))
    for f in range(F(T_PULL0 - 0.2), F(T_PULL1 + 0.4) + 1):
        t = (f - 1) / FPS
        data._k('spine', t, rot=(0, 0, lean_sgn * (spine_lean(t) if t < T_PULL1 + 0.05 else -4 * (1 - ease((t - T_PULL1) / 0.35)))))
    sc.frame_set(F(T_GRIP)); bpy.context.view_layer.update()
    sA = min("LR", key=lambda s: (acts._shoulder(data, s) - grip_pt(T_GRIP, 0)).length); sB = "R" if sA == "L" else "L"
    R_ = 0.995 * (data.U + data.Fo) * data.arm.scale.x
    def rest(t, s_):                       # the hand hanging out at his side, clear of the coat
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        sh_ = acts._shoulder(data, s_); fw = data.forward()
        o_ = Vector((-fw.y, fw.x, 0)); o_ = o_ if o_.dot(sh_ - data.pos()) > 0 else -o_
        near_post = (sh_ - data.pos()).dot(pdir) > 0      # the hand on the post's side hangs in, not into the post
        return sh_ + o_.normalized() * (0.04 if near_post else 0.1) + fw * (0.1 if near_post else 0.06) + Vector((0, 0, -0.84 * R_))
    def path(k, s_):                       # on the ball to T_LET, then carried down to his side by IK (no blend through the coat)
        def fn(t):
            if t <= T_LET: return grip_pt(t, k)
            return grip_pt(T_LET, k).lerp(rest(t, s_), ease((t - T_LET) / 0.45))
        return fn
    reach(data, sA, path(0, sA), T_GRIP, T_LET + 0.45, lead=0.35, back=0.3, elbow_out=0.75)
    reach(data, sB, path(1, sB), T_GRIP, T_LET + 0.45, lead=0.35, back=0.3, elbow_out=0.75)
    prog = lambda t: max(0.0, min(1.0, (lever_a(t) - A0) / (A1 - A0)))
    return prog, arm, to_cam, right, post_c


def tk_face_yaw(P=None, CA=None):
    """his facing at the lever, in degrees: three-quarters to the lens, turned to the post at his side"""
    P = P or TK_P; CA = CA or TK_CAM
    to_cam = Vector((CA.x - P.x, CA.y - P.y, 0)).normalized(); right = Vector((-to_cam.y, to_cam.x, 0))
    face = (to_cam - right * 0.45).normalized()
    return math.degrees(math.atan2(face.x, -face.y))


def tk_light():
    soft_key("track key", (0.9, -1.6, 1.2), (TK_SW.x, TK_SW.y - 0.3, 0.15), energy=40, size=40)
    soft_key("cart key", (-0.9, -1.4, 1.1), (TK_LX, -0.1, 0.2), energy=30, size=34)


def tk_open(cart_at):
    """the opening: close on the cart on the left branch, its stencil big"""
    c = Vector(cart_at)
    return c + Vector((0.06, -0.95, 0.6)), c + Vector((0.02, 0.0, 0.15))


TK_LENS = 34                       # a longer lens from further back: the near carts and the far Data hold the same frame
TK_MED = (TK_CAM.copy(), Vector((0.12, 0.12, 0.32)))     # the medium: Data, the lever, the right branch
TK_TWO = (Vector((0.08, -1.5, 1.04)), Vector((0.08, 0.12, 0.32)))    # the end: Data and the right branch, close (a cart there, or nothing)


def tk_camera(keys, focus, lens_keys=None):
    """keys: [(t, cam, look)], eased between; lens_keys: [(t, mm)]"""
    def at(t):
        if t <= keys[0][0]: return keys[0][1], keys[0][2]
        for (ta, ca, la), (tz, cz, lz) in zip(keys, keys[1:]):
            if t <= tz:
                u = ease((t - ta) / max(1e-6, tz - ta)); return ca.lerp(cz, u), la.lerp(lz, u)
        return keys[-1][1], keys[-1][2]
    c0, l0 = at(0.0)
    cam = K.camera(tuple(c0), tuple(l0), lens=(lens_keys[0][1] if lens_keys else 26), fstop=5.6)
    camera_path(cam, lambda t: (*at(t), focus(t) if callable(focus) else focus))
    for t, mm in (lens_keys or []):
        cam.data.lens = mm; cam.data.keyframe_insert("lens", frame=max(1, F(t)))
    return cam


# ================================================================ SHOT 3: it happened before


# ================================================================ SHOT 3: it happened before
def shot3():
    """THE GROS MICHEL, AND THE SWITCH. A 1950 banana railway: a stem runs back into the plantation and forks at a
    set of points into two branches that come toward us, each ending at a buffer stop. On the left branch stands a
    cart of big old bananas, its crate stencilled GROS MICHEL 1950: the fruit goes black, dead. Data, at the switch
    lever by the right branch, looks from it to us, takes the lever, winds it back and hauls it over: the red throw
    rod slides, the blades swing, and a fresh cart stencilled CAVENDISH, bright yellow, rolls down the stem, through
    the points and along the right branch to stop at the front beside the dead one. Relief."""
    where = place("plantation")
    M = tk_mats(); tk_clear()
    tk_track("tk stem", tk_stem(), M); tk_track("tk left", tk_left(), M); tk_track("tk right", tk_right(), M)
    tk_buffer("tk left buffer", TK_LX, M); tk_buffer("tk right buffer", TK_SW.x, M)
    T_ROT0, T_ROT1 = 0.1, 0.9                            # the dead fruit is a beat, not the shot (the other shots rot)
    T_GRIP, T_PULL0, T_PULL1 = 1.9, 2.75, 3.4             # a long wind-up, then a HAUL with his weight in it
    T_LET = T_PULL1 + 0.9                                 # he keeps hold of it, down, as the cart comes
    T_GO, T_STOP = T_PULL1 + 0.05, T_PULL1 + 2.3           # the new cart rolls in, and settles at the front
    gm = PR.skin_mat("gros michel", base="#E9C640", neck="#A9B23A")
    old, old_f = tk_cart("tk old cart", "GROS MICHEL", gm, M, seed=60, year="1950")
    OLD = Vector((TK_LX, TK_END + 0.3, 0)); old.location = OLD
    PR.rot(gm, T_ROT0, T_ROT1, to=1.0)
    cav = PR.skin_mat("cavendish", base="#F2D43C", neck="#9DBA3A")
    new, new_f = tk_cart("tk new cart", "CAVENDISH", cav, M, seed=80)
    path = tk_stem(3.4) + tk_right()[1:]
    d_stop = sum((b - a).length for a, b in zip(path, path[1:])) - 0.3     # it stops 0.3 m short of the right buffer
    def s_of(t):
        if t < T_GO: return 0.0
        u = min(1.0, (t - T_GO) / (T_STOP - T_GO)); s = d_stop * (1 - (1 - u) ** 2.4)
        if t > T_STOP: s = d_stop + 0.015 * math.exp(-6 * (t - T_STOP)) * math.sin(12 * (t - T_STOP))   # it rocks on its springs
        return s
    data = load_data()
    data.place(TK_P.x, TK_P.y, tk_face_yaw())
    sc.frame_set(1); bpy.context.view_layer.update()
    prog, lever, to_cam, right, post = tk_lever(data, T_GRIP, T_PULL0, T_PULL1, T_LET)
    sw = lambda t: ease(min(1.0, max(0.0, (prog(t) - 0.3) / 0.6)))     # the blades go over with the haul
    piv, rod = tk_points(M, sw, post)
    tk_run(new, path, s_of)
    US = tuple(TK_CAM)
    oldc = tuple(OLD + Vector((0, 0, 0.25)))
    data.look_at(oldc, 0.0, max_yaw=40, blend=0.0)              # the dead Gros Michel cart
    data.look_at(US, T_ROT1 + 0.1, max_yaw=40)                  # to us: dead, all of it
    data.look_at(US, T_PULL0 - 0.15, max_yaw=40)                # watch this
    data.look_at((TK_SW.x, 1.8, 0.25), T_PULL1 + 0.2, max_yaw=60)   # the new cart coming in from behind him
    data.look_at((TK_RX, TK_END + 0.3, 0.25), T_STOP - 0.4, max_yaw=50)   # ... past him, to the front
    data.look_at(US, T_STOP + 0.3, max_yaw=40)                  # to us, relieved
    data.idle(T_LET + 0.5, DUR)
    data.expression("worried", 0.3, T_PULL0 - 0.2)
    data.expression("happy", T_PULL1 + 0.6, T_STOP + 0.9)
    for t_ in [T_STOP + 1.1 + 0.2 * i for i in range(int((DUR - T_STOP - 1.1) / 0.2) + 1)] + [DUR]:
        data._face(t_, smile=0.12, open=0, oh=0, brow=0.1, lid=0.15, frown=0.25)   # relief settles to a knowing look: for now
    for tt, nd in ((T_STOP + 0.35, 0), (T_STOP + 0.55, 13), (T_STOP + 0.8, -2), (T_STOP + 1.0, 0)):   # a nod to us: saved
        data._k('neck', tt, rot=(nd, 0, 0))
    data.blink(1.0); data.blink(T_GRIP + 0.6)
    data.finish()
    tk_light()
    CO, LO = tk_open(OLD)
    T_MOVE0, T_MOVE1 = 0.9, 1.75                                  # close on the dead cart, then the whole fork and him
    C2 = TK_MED[0] + Vector((-0.02, 0.06, -0.01))
    T_TWO0 = T_STOP - 0.6; T_TWO1 = T_STOP + 0.6
    tk_camera([(0.0, CO, LO), (T_MOVE0, CO + Vector((0, 0.06, 0)), LO), (T_MOVE1, *TK_MED), (T_TWO0, C2, TK_MED[1]), (T_TWO1, *TK_TWO), (DUR, TK_TWO[0] + Vector((0, 0.04, 0)), TK_TWO[1])],
              lambda t: Vector(oldc) if t < T_MOVE0 + 0.3 else Vector((TK_P.x - 0.1, TK_P.y, 0.4)),
              lens_keys=[(0.0, 28), (T_MOVE0, 28), (T_MOVE1, TK_LENS), (T_TWO1, TK_LENS)])
    return dict(**where, data=data, rest=1, grips=("lever",), cutaway=(0.0, T_MOVE0),
                conseq=[("the Gros Michel fruit is dead", lambda: meshes([old]), T_ROT0, T_ROT1),
                        ("the lever is thrown and the points move", lambda: meshes([lever, rod] + piv), T_PULL0, T_PULL1 + 0.3),
                        ("the Cavendish cart rolls in on the new branch", lambda: meshes([new]), T_GO + 0.5, DUR)])


# ================================================================ SHOT 4: the new strain
def shot4():
    """NO CURE, IN THE SOIL FOR DECADES. The field cut open like a dig site: we stand in the trench and look at the
    ground in SECTION, its layers bare to the lens. On top a healthy young banana plant; in the soil under its roots a
    cloud of fungus spores glows, waiting. Data, beside the plant, sprays it with a big pump sprayer: the mist hits the
    leaves and nothing changes, the spores glow on. Beside him a calendar on a stake loses a page every five years
    (2026 ... 2056), each page falling to the ground. He gives up: drops the useless sprayer and shrugs to us."""
    # take 1 of the NEW shot 4 (caaleb 2026-11-13, of the old five shots: "all those were just varying shots of bananas
    # getting browner"): this beat is "no cure" (the spray does nothing) and "decades in the soil" (the spores wait
    # while the years go), and nothing in it browns.
    import bmesh
    where = place("field")
    FACE_Y, DEPTH = -0.36, 0.5                 # the cut face of the ground, and how deep the trench is
    for o in [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith("tree ") and o.location.y < 3.2]:
        for c in list(o.children_recursive): bpy.data.objects.remove(c, do_unlink=True)   # open soil behind him: the young
        bpy.data.objects.remove(o, do_unlink=True)                                         # plant reads against it, not lost in a canopy
    g = bpy.data.objects.get("field ground")
    if g: bpy.data.objects.remove(g, do_unlink=True)
    soil = LOC._noise_mat("field soil", "#5A4430", "#47362A", scale=1.0, rough=0.95, bump=0.35)
    K.box("field ground cut", (0, FACE_Y + 12, -0.01), (40, 24, 0.02), soil, bev=0)
    layers = [("topsoil", "#3E2C20", "#4A3426", 0.0, 0.12), ("subsoil", "#6B4E34", "#5C4330", 0.12, 0.3),
              ("clay", "#8A6A48", "#7A5C3E", 0.3, DEPTH + 0.05)]
    for nm, a, b, z0, z1 in layers:            # the section: three bands of earth, the face open to the lens
        m = LOC._noise_mat(f"cut {nm}", a, b, scale=9.0, rough=0.97, bump=0.6)
        K.box(f"ground cut {nm}", (0, FACE_Y + 0.06, -(z0 + z1) / 2), (8, 0.12, z1 - z0), m, bev=0)
    for i in range(14):                        # stones in the face
        rnd = random.Random(70 + i)
        K.sph("cut stone", (rnd.uniform(-1.2, 1.2), FACE_Y + 0.004, -rnd.uniform(0.08, DEPTH - 0.03)), 1.0,
              K.mat("cut stone", "#8C847A", rough=0.8), scale=(rnd.uniform(0.012, 0.03), 0.012, rnd.uniform(0.01, 0.022)))
    K.box("trench floor", (0, FACE_Y - 6, -DEPTH - 0.01), (40, 12, 0.02), LOC._noise_mat("trench floor", "#5C4532", "#4E3A2B", scale=2.0, rough=0.95, bump=0.3), bev=0)
    # the plant, right at the edge so its roots run down the face
    PX, PY = -0.3, FACE_Y + 0.1
    # take 2 (judge 52): "a bare green pole ... it reads as a post" -> a field banana plant at a young size: a tapering
    # trunk and broad paddle leaves fanning ABOVE, every leaf that would cross his head or the lens taken off
    tree = LOC.banana_tree("young plant", (PX, PY, -0.05), h=0.85, seed=12, n_leaves=9)
    bpy.context.view_layer.update()
    for lo in [c for c in tree.children if " leaf " in c.name]:
        a_ = tree.rotation_euler.z + lo.rotation_euler.z
        if math.cos(a_) > 0.7 or math.sin(a_) < -0.85:
            bpy.data.objects.remove(lo, do_unlink=True)
    root_m = K.mat("plant roots", "#C9B48A", rough=0.8)
    for k, (dx, dz) in enumerate(((-0.12, -0.2), (-0.05, -0.27), (0.04, -0.24), (0.12, -0.18), (0.0, -0.32), (-0.18, -0.12), (0.17, -0.1))):
        K.capsule("plant root", (PX + dx * 0.15, FACE_Y + 0.003, -0.01), (PX + dx, FACE_Y + 0.003, dz), 0.006, root_m, ra=0.009, rb=0.003)
    FLIPS = [0.55 + (0.7 * DUR - 0.55) * k / 5 for k in range(6)]   # the calendar's tears (as below): the spores flare at each
    # THE SPORES: a cloud of glowing specks in the soil under the roots, pulsing slowly the whole shot
    spore_m = K.mat("tr4 spores", "#C66BFF", rough=0.4, emit=6.0)
    halo_m = K.mat("tr4 spore halo", "#7A2FB0", rough=0.6, emit=1.6)
    spores = []
    rnd = random.Random(404)
    for i in range(70):
        u = rnd.random(); x = PX + rnd.gauss(0, 0.19); z = -0.06 - (DEPTH - 0.1) * (u ** 0.8)
        r = rnd.uniform(0.007, 0.016)
        spores.append(K.sph("tr4 spore", (x, FACE_Y + 0.004, z), r, spore_m, seg=10, ring=6))
        if i % 3 == 0:
            spores.append(K.sph("tr4 spore halo", (x, FACE_Y + 0.006, z), r * 2.3, halo_m, scale=(1, 0.3, 1), seg=12, ring=6))
    try:
        es = spore_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f in range(1, NF + 1, 3):
            t = (f - 1) / FPS; es.default_value = 6.0 + 3.0 * math.sin(t * 2 * math.pi / 1.6) + 7.0 * sum(math.exp(-(t - c) / 0.3) for c in FLIPS if t >= c); es.keyframe_insert("default_value", frame=f)
    except (KeyError, AttributeError):
        pass
    K.text("tr4 label", "TR4 FUNGUS", (PX + 0.5, FACE_Y - 0.002, -0.33), 0.06, (math.radians(90), 0, 0),
           K.mat("tr4 label ink", "#E7C9FF", rough=0.5, emit=2.5), extrude=0.001)
    # THE CALENDAR on a stake beside him: a page every five years, each one falling to the ground
    CX, CY, PH_, PW = 0.33, FACE_Y + 0.3, 0.22, 0.2
    cz = 0.34                                   # take 2: below his head, beside his body (it hid behind his head)
    K.box("calendar stake", (CX, CY + 0.012, cz / 2), (0.03, 0.03, cz + PH_ / 2), K.mat("stake wood", "#7C6146", rough=0.85), bev=0.003)
    K.box("calendar back", (CX, CY, cz), (PW + 0.03, 0.012, PH_ + 0.08), K.mat("calendar board", "#3A3D42", rough=0.6), bev=0.003)
    K.box("calendar band", (CX, CY - 0.012, cz + PH_ / 2 + 0.02), (PW + 0.03, 0.012, 0.05), K.mat("sale red", "#C6392B", rough=0.5), bev=0.002)
    paper = K.mat("calendar paper", "#F4F1EA", rough=0.8); ink = K.mat("sign navy")
    years = list(range(2026, 2057, 5)); tY0, tY1 = 0.55, 0.7 * DUR
    flips = [tY0 + (tY1 - tY0) * k / (len(years) - 2) for k in range(len(years) - 1)]
    top = cz + PH_ / 2 - 0.006
    for k, yr in enumerate(years):
        y = CY - 0.009 - 0.0032 * (len(years) - k)
        piv = K.empty(f"page {yr}", (CX, y, top))
        K.box(f"page sheet {yr}", (CX, y, top - PH_ / 2), (PW, 0.0012, PH_), paper, bev=0, parent=piv)
        K.text(f"year {yr}", str(yr), (CX, y - 0.0011, top - PH_ / 2 - 0.01), 0.095, (math.radians(90), 0, 0), ink, extrude=0.0004, parent=piv)
        if k < len(flips):
            props.tear_off(piv, NF, flips[k], (0, -1, 0), floor_z=0.0, seed=k + 11, page_h=PH_, side_drift=(0.04, 0.12),
                           layer=k, hold_s=0.0, carry=(0.0, 0.0, 0.0), out_drift=(0.0, 0.06))
    # Data between the plant and the calendar, turned a little toward the plant, face to us
    data = load_data()
    DP = Vector((0.08, FACE_Y + 0.2, 0)); data.place(DP.x, DP.y, -30)
    sc.frame_set(1); bpy.context.view_layer.update()
    AIM = Vector((PX + 0.03, PY, 0.5))        # the leaves he sprays
    side = near_hand(data, AIM)
    REACH = 0.995 * (data.U + data.Fo)        # U and Fo are already in world metres (the rig is scaled 0.2)
    PUFFS = (0.3, 0.85, 1.4, 1.95, 2.5)
    T_LOW = PUFFS_END = 3.0                     # take 2: he keeps the sprayer; after the last squeeze it sinks to his side
    def grip(t):                                # the sprayer's handle in his hand: held out toward the plant, a little bob with each squeeze
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        sh = acts._shoulder(data, side); to = (AIM - sh); to.z = 0; to.normalize()
        squeeze = 0.012 * sum(math.exp(-((t - p) / 0.08) ** 2) for p in PUFFS)
        up = sh + to * 0.74 * REACH + Vector((0, 0, -0.5 * REACH - squeeze))
        o_ = sh - data.pos(); o_.z = 0; o_.normalize()
        low = sh + to * 0.62 * REACH + o_ * 0.05 + Vector((0, 0, -0.76 * REACH))
        return up.lerp(low, ease(min(1.0, max(0.0, (t - T_LOW) / 0.45))))
    # the sprayer: a yellow pump tank under a pistol grip, a long wand out to the nozzle (grip at the origin, wand along +X)
    sp = K.empty("sprayer", (0, 0, 0))
    yel = K.mat("sprayer tank", "#E8B92E", rough=0.45); blk = K.mat("sprayer black", "#26282B", rough=0.5)
    K.box("sprayer grip", (0, 0, -0.035), (0.035, 0.04, 0.08), blk, bev=0.01, parent=sp)
    K.cyl("sprayer tank body", (0.1, 0, -0.1), 0.065, 0.18, yel, v=28, bev=0.012, parent=sp)
    K.cyl("sprayer tank cap", (0.1, 0, 0.0), 0.03, 0.025, blk, v=16, parent=sp)
    K.box("sprayer label", (0.1, -0.066, -0.1), (0.07, 0.004, 0.08), K.mat("sprayer label", "#2E7D3A", rough=0.5), bev=0.002, parent=sp)
    wand = K.cyl("sprayer wand", (0.2, 0, 0.005), 0.011, 0.36, K.mat("sprayer wand", "#9AA0A6", rough=0.3, metal=0.8), rot=(0, math.radians(90), 0), v=12, parent=sp)
    K.cyl("sprayer nozzle", (0.39, 0, 0.005), 0.018, 0.04, blk, rot=(0, math.radians(90), 0), v=12, parent=sp)
    noz = K.empty("sprayer nozzle tip", (0.41, 0, 0.005), parent=sp)
    mist_m = bpy.data.materials.get("spray mist") or bpy.data.materials.new("spray mist")
    mist_m.use_nodes = True
    try:
        bs = mist_m.node_tree.nodes["Principled BSDF"]; bs.inputs["Base Color"].default_value = (0.92, 0.96, 1.0, 1)
        bs.inputs["Alpha"].default_value = 0.45; bs.inputs["Roughness"].default_value = 0.3
        mist_m.blend_method = 'BLEND'
    except (KeyError, AttributeError):
        pass
    mists = []
    for j, p in enumerate(PUFFS):              # each squeeze: a cone of mist bursts out of the nozzle and fades
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=20, radius1=0.004, radius2=0.09, depth=0.3)
        me = bpy.data.meshes.new(f"spray mist {j}"); bm.to_mesh(me); bm.free(); me.materials.append(mist_m)
        for pl in me.polygons: pl.use_smooth = True
        mo = bpy.data.objects.new(f"spray mist {j}", me); bpy.context.collection.objects.link(mo)
        mo.parent = noz; mo.location = (0.15, 0, 0); mo.rotation_euler = (0, math.radians(90), 0)
        for f in range(1, NF + 1):
            t = (f - 1) / FPS; u = (t - p) / 0.5
            on = 0.0 <= u <= 1.0
            s = (0.15 + 0.85 * min(1.0, u / 0.35)) if on else 0.001
            mo.scale = (s, s, max(0.001, s if on else 0.001)); mo.keyframe_insert("scale", frame=f)
            mo.hide_render = not on; mo.keyframe_insert("hide_render", frame=f)
        mists.append(mo)
    def sprayer_pose(t):
        g_ = grip(t); u = ease(min(1.0, max(0.0, (t - T_LOW) / 0.45)))
        down = Vector((AIM.x, AIM.y, 0.1))                          # lowered, the wand sags toward the soil
        tgt = AIM.lerp(down, u); d = (tgt - g_).normalized()
        return g_, d.to_track_quat('X', 'Z').to_euler()
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; g_, r_ = sprayer_pose(t)
        sp.location = g_; sp.rotation_euler = r_; sp.keyframe_insert("location", frame=f); sp.keyframe_insert("rotation_euler", frame=f)
    reach(data, side, grip, 0.0, DUR, lead=0.05, back=0.3, elbow_out=0.5)
    # the DROPLETS (take 2, judge: "no spray at all ... droplets falling to the soil and stopping at the surface line
    # while the spores keep pulsing below"): every squeeze throws a burst at the leaves; they drip to the soil and
    # sit on its surface, never reaching the spores
    drop_m = K.mat("spray droplet", "#DDF2FF", rough=0.05, emit=0.6)
    drops = []
    for j, p in enumerate(PUFFS):
        sc.frame_set(F(p)); bpy.context.view_layer.update(); n0 = noz.matrix_world.translation.copy()
        rnd_ = random.Random(900 + j)
        for i in range(24):
            o = K.sph("spray droplet", tuple(n0), rnd_.uniform(0.008, 0.013), drop_m, seg=8, ring=5); drops.append(o)
            hitp = AIM + Vector((rnd_.uniform(-0.12, 0.12), rnd_.uniform(-0.05, 0.08), rnd_.uniform(-0.12, 0.08)))
            land = Vector((hitp.x + rnd_.uniform(-0.04, 0.04), min(hitp.y, FACE_Y + 0.11), 0.006))
            t_fly = p + rnd_.uniform(0.0, 0.18); t_hit = t_fly + 0.22; t_land = t_hit + rnd_.uniform(0.25, 0.4)
            for f in range(1, NF + 1):
                t = (f - 1) / FPS
                if t < t_fly: q = n0; vis = False
                elif t < t_hit: q = n0.lerp(hitp, (t - t_fly) / 0.22); vis = True
                elif t < t_land: u = (t - t_hit) / (t_land - t_hit); q = hitp.lerp(land, u * u); vis = True
                else: q = land; vis = t < t_land + 1.2
                o.location = q; o.keyframe_insert("location", frame=f); o.hide_render = not vis; o.keyframe_insert("hide_render", frame=f)
    US = (0.0, -1.9, 0.3)
    data.look_at(AIM, 0.0, max_yaw=30, blend=0.0)
    data.look_at((CX, CY, cz), flips[1] - 0.1, max_yaw=30)          # a glance at the years going by
    data.look_at(AIM, flips[1] + 0.45, max_yaw=30)                   # back to the plant: still nothing
    data.look_at((PX + 0.1, FACE_Y, -0.2), T_LOW + 0.3, max_yaw=30, max_pitch=30)   # down at the soil: the spores, untouched
    data.look_at(US, T_LOW + 0.95, max_yaw=30)                                     # then to us: nothing works
    for j, dx in enumerate((-0.25, 0.25, 0.0)):                                    # a slow head shake: no
        data.look_at((US[0] + dx, US[1], US[2]), T_LOW + 1.2 + 0.18 * j, max_yaw=30)
    data.idle(0.0, DUR)
    data.expression("worried", 0.3, DUR)
    for i in range(int((DUR - T_LOW) / 0.2) + 1):
        data._face(T_LOW + 0.2 * i, smile=0, open=0, oh=0, brow=0.14, lid=0.25, frown=1.0)
    data._k("spine", 0.0, rot=(0, 0, 0)); data._k("spine", T_LOW + 0.2, rot=(0, 0, 0)); data._k("spine", T_LOW + 0.7, rot=(7, 0, 0)); data._k("spine", DUR, rot=(6, 0, 0))
    data.blink(1.3); data.blink(T_LOW + 0.6)
    data.finish()
    soft_key("plant key", (-0.7, -1.4, 0.9), (PX, PY, 0.35), energy=40, size=30)
    soft_key("face key", (0.2, -1.6, 0.2), (PX, FACE_Y, -0.25), energy=30, size=40)
    C0, C1 = Vector((-0.06, -1.66, 0.34)), Vector((-0.06, -1.58, 0.34))
    LK0 = Vector((-0.06, FACE_Y, 0.24))
    cam = K.camera(tuple(C0), tuple(LK0), lens=24, fstop=5.6)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK0, (DP.x - 0.1, FACE_Y, 0.2)))
    sheets = [o for o in bpy.data.objects if o.name.startswith("page sheet ")]
    return dict(**where, data=data, rest=1, grips=("sprayer",),
                conseq=[("the spray mists the plant", mists + drops, PUFFS[0], PUFFS[-1] + 0.5),
                        ("the spores glow on under it", spores, 0.0, DUR),
                        ("the years fall off the calendar", sheets, flips[0], DUR)])


# ================================================================ SHOT 5: no banana to switch to
# shot 5's own rail: it recedes almost straight away from the lens at his right hand, so the rot comes TOWARD the
# camera and him, and the whole row, the box under its far end and Data fit one frame (no pan)
S5_YAW = 62
S5_R0 = (0.0, -0.78)
S5_DP, S5_DROT = Vector((-0.22, -0.74, 0)), 15
S5_C0, S5_LK0 = Vector((0.0, -1.95, 0.64)), Vector((0.0, -0.2, 0.40))


def shot5():
    """THE PAYOFF: THE SAME SWITCH, AND NOTHING TO SWITCH TO. The Ecuador export dock, the same little railway as the
    1950 shot: on the left branch a cart of bright bananas stencilled ECUADOR, and a dark fungus stain creeping across
    the quay to it; its fruit goes black. Data hauls the SAME lever the same way, and a cart rolls in on the new branch
    exactly as the Cavendish cart did in 1950: this time its crate is EMPTY. There is no banana to switch to. He looks
    into it, then turns to us, out of options, and shrugs."""
    # take 3 (judge 52-64, every judge: "'switches to nothing' is never SEEN, it rests on a small sign"; a derailing cart
    # read as a glitch). The callback to shot 3 now carries it on screen: the same haul brings the same kind of cart, and
    # the picture of "no banana to switch to" is the empty crate it brings.
    where = place("dock")
    M = tk_mats(); tk_clear()
    tk_track("tk stem", tk_stem(), M); tk_track("tk left", tk_left(), M); tk_track("tk right", tk_right(), M)
    tk_buffer("tk left buffer", TK_LX, M); tk_buffer("tk right buffer", TK_SW.x, M)
    T_GRIP, T_PULL0, T_PULL1 = 1.7, 2.4, 2.95
    T_LET = T_PULL1 + 0.8
    T_GO, T_STOP = T_PULL1 + 0.05, T_PULL1 + 1.9
    fruit = PR.skin_mat("ecuador fruit", base="#F2D43C", neck="#9DBA3A")
    cart, cf = tk_cart("tk ecuador cart", "ECUADOR", fruit, M, seed=90)
    OLD = Vector((TK_LX, TK_END + 0.3, 0)); cart.location = OLD
    T_REACH = 1.5
    PR.rot(fruit, T_REACH, T_REACH + 1.2, to=0.95)
    for i, (x, y) in enumerate(((-0.55, 0.9), (-0.55, 1.25))):          # the export boxes waiting on the quay
        PR.produce_box(f"quay box {i}", (x, y, 0.0), yaw=0.0)
        PR.produce_box(f"quay box top {i}", (x, y, 0.18), yaw=0.0)
    # the next cart, the one that should bring the next banana: EMPTY
    blank = PR.skin_mat("no fruit", base="#F2D43C", neck="#9DBA3A")
    new, new_f = tk_cart("tk empty cart", "?", blank, M, seed=81)
    for o in list(new.children_recursive):
        if " bunch " in o.name: o.hide_render = True; o.hide_viewport = True
    path = tk_stem(3.4) + tk_right()[1:]
    d_stop = sum((b - a).length for a, b in zip(path, path[1:])) - 0.3
    def s_of(t):
        if t < T_GO: return 0.0
        u = min(1.0, (t - T_GO) / (T_STOP - T_GO)); s = d_stop * (1 - (1 - u) ** 2.4)
        if t > T_STOP: s = d_stop + 0.015 * math.exp(-6 * (t - T_STOP)) * math.sin(12 * (t - T_STOP))
        return s
    tk_run(new, path, s_of)
    # THE STAIN: dark mould, fuzzy-edged, opening spot after spot from the export boxes across the quay to the cart
    fm = LOC._noise_mat("dock fungus", "#0E0A06", "#3A2E1C", scale=6.0, rough=1.0, bump=0.6)
    rnd = random.Random(12); blobs = []
    A_, B_ = Vector((-0.5, 0.62, 0)), Vector((OLD.x + 0.04, OLD.y - 0.02, 0))
    N_ = 8
    for i in range(N_):
        p_ = A_.lerp(B_, i / (N_ - 1)) + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0))
        r = 0.09 + 0.03 * rnd.random(); t0 = 0.1 + (T_REACH - 0.4) * i / (N_ - 1)
        o_ = K.sph(f"fungus stain {i}", (p_.x, p_.y, 0.003), 1.0, fm, scale=(0.001, 0.001, 0.004))
        o_.keyframe_insert("scale", frame=1); o_.keyframe_insert("scale", frame=max(1, F(t0)))
        for k in range(1, 5):
            e = k / 4; o_.scale = (r * e * 1.15, r * e, 0.004); o_.keyframe_insert("scale", frame=F(t0 + 0.5 * e))
        blobs.append(o_)
    data = load_data()
    data.place(TK_P.x, TK_P.y, tk_face_yaw())
    sc.frame_set(1); bpy.context.view_layer.update()
    prog, lever, to_cam, right, post = tk_lever(data, T_GRIP, T_PULL0, T_PULL1, T_LET)
    sw = lambda t: ease(min(1.0, max(0.0, (prog(t) - 0.3) / 0.6)))
    piv, rod = tk_points(M, sw, post)
    US = tuple(TK_CAM)
    oldc = tuple(OLD + Vector((0, 0, 0.25)))
    newc = (TK_RX, TK_END + 0.3, 0.2)
    data.look_at(oldc, 0.0, max_yaw=40, blend=0.0)                   # the stain reaching the Ecuador cart
    data.look_at(US, T_REACH + 0.2, max_yaw=40)                       # to us: it's here
    data.look_at((TK_SW.x, 1.8, 0.25), T_PULL1 + 0.15, max_yaw=60)    # the next cart coming, as before
    data.look_at(newc, T_STOP - 0.4, max_yaw=50)                      # ... and into it: empty
    data.look_at(US, T_STOP + 0.7, max_yaw=40)                        # to us: nothing to switch to
    T_SHRUG = T_STOP + 1.0
    data.idle(T_LET + 0.5, DUR)
    data.expression("worried", 0.2, T_STOP - 0.2)
    data.expression("alarmed", T_STOP - 0.2, T_SHRUG)
    data.act("shrug", T_SHRUG, dur=0.3, hold=max(0.4, DUR - T_SHRUG - 0.4))
    for t_ in [T_SHRUG + 0.2 * i for i in range(int((DUR - T_SHRUG) / 0.2) + 1)] + [DUR]:
        data._face(t_, smile=0, open=0, oh=0, brow=0.12, lid=0.25, frown=1.0)
    data.blink(1.0); data.blink(T_GRIP + 0.6)
    data.finish()
    tk_light()
    CO, LO = tk_open(OLD)
    T_MOVE0, T_MOVE1 = 0.9, 1.6
    C2 = TK_MED[0] + Vector((-0.02, 0.06, -0.01))
    T_TWO0 = T_STOP - 0.6; T_TWO1 = T_STOP + 0.5
    tk_camera([(0.0, CO, LO), (T_MOVE0, CO + Vector((0, 0.06, 0)), LO), (T_MOVE1, *TK_MED), (T_TWO0, C2, TK_MED[1]), (T_TWO1, *TK_TWO), (DUR, TK_TWO[0] + Vector((0, 0.04, 0)), TK_TWO[1])],
              lambda t: Vector(oldc) if t < T_MOVE0 + 0.3 else Vector((TK_P.x - 0.1, TK_P.y, 0.4)),
              lens_keys=[(0.0, 28), (T_MOVE0, 28), (T_MOVE1, TK_LENS), (T_TWO1, TK_LENS)])
    return dict(**where, data=data, rest=1, grips=("lever",), cutaway=(0.0, T_MOVE0),
                conseq=[("the fungus creeps across the quay to the Ecuador cart", lambda: meshes(blobs), 0.3, T_REACH + 0.4),
                        ("the lever is thrown and the points move", lambda: meshes([lever, rod] + piv), T_PULL0, T_PULL1 + 0.3),
                        ("the next cart rolls in on the new branch, EMPTY", lambda: meshes([new]), T_GO + 0.5, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


