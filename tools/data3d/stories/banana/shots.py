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
RAIL_Y, RAIL_Z = -0.22, 0.78           # the hanging rail (shots 2 and 5)


def produce_set(lanes_x=(2.4, 3.0)):
    """the approved store, with the produce stand at the front; two lanes stay far off to the right of frame so the
    room still reads as the same supermarket"""
    lanes, kiosks, clerks = build_set(list(lanes_x), ())
    return lanes, kiosks


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
            if p.z <= floor_z + 0.012:
                p.z = floor_z + 0.012; landed += 1; v = Vector((v.x * 0.5, v.y * 0.5, -v.z * bounce)); w *= 0.4
                if landed == 2: v = Vector((0, 0, 0))
            r = Vector((r0.x, r0.y, r0.z)) + w * (t - t_drop)
            if landed == 2: r.x = math.radians(90) * round(r.x / math.radians(90)); r.y = 0      # it settles lying on the board
        obj.location = p; obj.rotation_euler = tuple(r); obj.keyframe_insert("location", frame=f); obj.keyframe_insert("rotation_euler", frame=f)


# ================================================================ SHOT 1: the hook
def shot1():
    """THE SHOCK FIRST (CLAUDE.md, "the opening is the shock"): from frame one a bright bunch is held up in his hands
    and the black is already creeping over it. A medium CLOSE: his head and the bunch fill the frame. By 1.5 s it is
    brown and a finger drops off onto the table below; at 2.0 s he holds the bunch away at arm's length and leans
    back from it, brows up; he ends looking at us."""
    lanes, kiosks = produce_set()
    PR.table("produce table", (0.0, -0.36, 0.0), w=1.1, d=0.36, h=TABLE_H)
    fresh = PR.skin_mat("table")
    for k, (x, y, yaw) in enumerate(((-0.4, -0.42, 0.3), (-0.24, -0.3, -0.2), (0.25, -0.31, 2.9), (0.42, -0.42, 3.3))):
        r, _ = PR.bunch(f"table bunch {k}", (x, y, TABLE_H + 0.042), fresh, n=6, seed=10 + k, L=0.15)
        r.rotation_euler = (0, 0, yaw)
    hm = PR.skin_mat("hero")
    hero, fingers = PR.bunch("hero bunch", (0, 0, 0), hm, n=6, seed=3, L=0.24, spread=1.0)
    data = load_data()
    data.place(0.0, 0.02, 0)
    sc.frame_set(1); bpy.context.view_layer.update()
    sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
    mid = (sh["L"] + sh["R"]) / 2
    # the crown in both hands just below the chin, a little to his left so the fingers rise beside his face, not over it
    near = mid + Vector((0.1, -0.17, 0.04)); far = mid + Vector((0.16, -0.27, 0.03))   # held up at chest height, clear of the table
    T_ROT1, T_DROP, T_RECOIL = 1.9, 1.4, 2.0
    at = lambda t: near.lerp(far, ease((t - T_RECOIL) / 0.35))
    # fingers out to his side and up, the fan spread flat to the lens so every finger is its own shape (fingers stood
    # up and curving at the lens fanned into one blob; once black it read as a glove or a boot)
    tilt = lambda t: (math.radians(90), math.radians(-38 - 10 * ease((t - T_RECOIL) / 0.35)), 0)   # the fan FACES the lens: five fingers spread like a hand
    follow(hero, at, 0.0, DUR, rot_fn=tilt)
    PR.rot(hm, 0.0, T_ROT1, to=0.8, frm=0.1)   # black-brown with its spots still showing: fully black lost every finger's shape               # already freckled on frame one: the threat is there at once
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; c = at(t)
        for s_ in "LR":
            sx = -1 if sh[s_].x < mid.x else 1
            data._arm_ik(s_, c + Vector((sx * 0.05 - 0.01, 0.02, -0.04 if sx > 0 else -0.01)), t, 0.4)
    data._k("spine", 0.0, rot=(0, 0, 0)); data._k("spine", T_RECOIL, rot=(0, 0, 0)); data._k("spine", T_RECOIL + 0.3, rot=(-8, 0, -5)); data._k("spine", DUR, rot=(-7, 0, -4))
    look = lambda t: at(t) + Vector((0.0, 0.0, 0.12))
    data.look_at(look(0.0), 0.0, max_yaw=30, blend=0.0)
    data.look_at(look(T_DROP), T_DROP + 0.1, max_yaw=30)
    data.look_at(far + Vector((0, 0, 0.1)), T_RECOIL + 0.35, max_yaw=30)
    data.look_at((0.0, -2.0, 0.7), DUR - 0.45, max_yaw=30)          # then to us
    data.expression("worried", 0.0, T_RECOIL - 0.25)
    data.expression("surprised", T_RECOIL - 0.1, DUR)
    data.blink(0.85); data.blink(DUR - 0.3)
    data.finish()
    drop(fingers[0], T_DROP, TABLE_H + 0.034, kick=(0.22, -0.12, 0.2), spin=(3, 1, 5))   # one finger lets go: it lands on the table
    soft_key("bunch key", (0.5, -1.0, 0.9), tuple(near), energy=24, size=22)
    C0, C1, LK = Vector((0.08, -1.0, 0.68)), Vector((0.05, -0.9, 0.66)), Vector((0.03, -0.1, 0.55))
    cam = K.camera(tuple(C0), tuple(LK), lens=32, fstop=3.2)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, near))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("hero bunch",),
                conseq=[("the bunch goes black in his hands", fingers[1:], 0.0, T_ROT1),
                        ("a finger drops onto the table", [fingers[0]], T_DROP, DUR)])


# ================================================================ the rail (shots 2 and 5)
RAIL0, RAIL_YAW, RAIL_LEN, N_HOOK = (-0.2, -0.8), 55, 1.0, 6      # it runs from just in front of him to the right and back: diagonal to the lens, and he faces us over it


# where he stands for the rail beats: BESIDE the rail's near end, level with it, turned a little to it, so the row runs away
# behind his shoulder and nothing on it ever hangs between his face and the lens (the first layout stood him behind
# the rail with a bunch over his face for the whole beat: staging.face_hidden now refuses that)
RAIL_DP, RAIL_DROT = Vector((-0.38, -0.8, 0)), 20
RAIL_C0, RAIL_LK = Vector((-0.2, -1.85, 0.62)), Vector((-0.12, -0.6, 0.5))   # him on the left third, the row receding past his shoulder to the right


def rail_row(m_of, sticker=True):
    """the hanging rail with a bunch on every hook; m_of(k) -> that bunch's skin. Every bunch carries the SAME blue
    sticker: the one fact of the beat (copies of one plant) on the fruit itself, not on a sign over it."""
    pivot, hooks = PR.rail_at("banana rail", RAIL0, RAIL_YAW, RAIL_LEN, RAIL_Z, N_HOOK)
    blue = K.mat("sticker", "#1F5FA8", rough=0.4); ink = K.mat("sticker ink", "#FFFFFF", rough=0.4)
    rows = []
    for k, (p, sw) in enumerate(hooks):
        root, fingers = PR.hang_bunch(f"rail bunch {k}", sw, m_of(k), seed=40 + (k % 2), L=0.2)   # big enough to read beside his head   # two seeds only: the bunches are COPIES
        if sticker:
            f0 = fingers[2]; bpy.context.view_layer.update()
            st = K.cyl(f"sticker {k}", (0, 0, 0), 0.014, 0.002, blue, v=20, bev=0)
            st.parent = f0; st.matrix_parent_inverse = Matrix.Identity(4); st.location = (0.075 * 0.2 / 0.13, 0, 0.0); st.rotation_euler = (math.radians(90), 0, 0)
            st.location.z += 0.02 * 0.2 / 0.13
        rows.append((p, sw, root, fingers))
    sign = K.box("rail sign", (0, 0, 0), (0.44, 0.012, 0.11), K.mat("rail sign board", "#F4EFE4", rough=0.5), bev=0.004)
    R = Matrix.Rotation(math.radians(RAIL_YAW), 3, 'Z'); mid = Vector((RAIL0[0], RAIL0[1], 0)) + R @ Vector((RAIL_LEN * 0.5, 0, 0))
    sign.location = (mid.x, mid.y, RAIL_Z + 0.16); sign.rotation_euler = (0, 0, math.radians(RAIL_YAW))
    K.text("rail sign text", "CAVENDISH", tuple(Vector((mid.x, mid.y, RAIL_Z + 0.16)) + R @ Vector((0, -0.0075, 0))), 0.06,
           (math.radians(90), 0, math.radians(RAIL_YAW)), K.mat("rail sign ink", "#1F5FA8", rough=0.5), extrude=0.001)
    for xp in (0.0, RAIL_LEN):
        c = Vector((RAIL0[0], RAIL0[1], 0)) + R @ Vector((xp, 0, 0))
        K.cyl("sign wire", (c.x, c.y, RAIL_Z + 0.11), 0.002, 0.1, K.mat("rail chrome"), v=6, bev=0)
    return rows


# ================================================================ SHOT 2: clones
def shot2():
    """COPIES OF ONE PLANT, AND WHAT KILLS ONE KILLS THEM ALL. A rail of identical bunches recedes from beside him,
    each with the same blue sticker. He pushes the nearest one and every bunch swings in turn, the SAME swing passed
    down the row (a row of copies moves as one). On "what kills one can kill them all" a brown blight starts on the
    first and runs down the row, bunch by bunch."""
    lanes, kiosks = produce_set()
    T_PUSH, T_BLIGHT = 1.05, DUR * 0.55
    mats = [PR.skin_mat(f"rail {k}") for k in range(N_HOOK)]
    rows = rail_row(lambda k: mats[k])
    for k, (p, sw, root, fingers) in enumerate(rows):
        PR.swing(sw, T_PUSH + 0.18 * k, amp_deg=20, period=0.95, tau=1.6, nf=NF)
        PR.rot(mats[k], T_BLIGHT + 0.22 * k, T_BLIGHT + 0.22 * k + 0.9, to=0.62)
    data = load_data()
    DP = RAIL_DP; data.place(DP.x, DP.y, RAIL_DROT)
    sc.frame_set(1); bpy.context.view_layer.update()
    side = near_hand(data, rows[0][0])
    # his hand goes to the first bunch, pushes it down the rail, comes back
    def bunch_side(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return rows[0][2].matrix_world.translation + Vector((0, 0, -0.07)) + Matrix.Rotation(math.radians(RAIL_YAW), 3, 'Z') @ Vector((-0.06, 0, 0))
    reach(data, side, lambda t: bunch_side(max(t, T_PUSH - 0.05)), T_PUSH - 0.2, T_PUSH + 0.18, lead=0.45, elbow_out=0.4)
    data.look_at(rows[0][0] + Vector((0, 0, -0.1)), 0.4, max_yaw=40)
    data.look_at(rows[3][0], T_PUSH + 0.6, max_yaw=40)            # he follows the swing down the row
    data.look_at(rows[5][0], T_PUSH + 1.1, max_yaw=40)
    data.look_at((DP.x - 0.25, -2.4, 0.75), T_BLIGHT - 0.3, max_yaw=40)   # to us: same plant
    data.look_at(rows[0][0] + Vector((0, 0, -0.1)), T_BLIGHT + 0.3, max_yaw=40)   # the blight starts
    data.look_at(rows[4][0], DUR - 0.2, max_yaw=40)
    data.idle(0.0, DUR)
    data.expression("happy", 0.3, T_BLIGHT)
    data.expression("worried", T_BLIGHT + 0.2, DUR)
    data.blink(0.6); data.blink(T_BLIGHT - 0.1); data.blink(DUR - 0.5)
    data.finish()
    soft_key("rail key", (0.9, -1.7, 1.1), (0.25, -0.62, 0.62), energy=40, size=34)
    C0, C1 = RAIL_C0, RAIL_C0 + Vector((0.04, 0.15, -0.02)); LK = RAIL_LK
    cam = K.camera(tuple(C0), tuple(LK), lens=26, fstop=4.5)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, rows[1][0]))
    swingers = [r[2] for r in rows]
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("rail bunch 0",),
                conseq=[("every bunch swings in turn", lambda: meshes(swingers), T_PUSH, T_PUSH + 1.6),
                        ("the blight runs down the row", lambda: meshes(swingers), T_BLIGHT, DUR)])


# ================================================================ SHOT 3: it happened before
def shot3():
    """THE GROS MICHEL. An old wooden crate on the table, GROS MICHEL / 1950 stencilled on it. He lifts its lid off and
    drops it aside: the fruit inside is fat and yellow for a beat, then goes black. He pushes the crate over on its
    side and the dead fruit spills out across the table."""
    lanes, kiosks = produce_set()
    PR.table("produce table", (0.0, -0.42, 0.0), w=1.0, d=0.5, h=TABLE_H)
    TOP = TABLE_H + 0.034
    CX, CY = 0.06, -0.36; cz = TABLE_H + 0.03; CW, CD, CH = 0.38, 0.26, 0.17
    cr = PR.crate("old crate", (CX, CY, cz), w=CW, d=CD, h=CH)
    piv = K.empty("crate tip", (CX + CW / 2, CY, cz)); root = cr["root"]          # it goes over on its RIGHT bottom edge, away from his face
    root.parent = piv; root.matrix_parent_inverse = piv.matrix_basis.inverted()
    lid = cr["lid"]; lid_m = lid.matrix_world.copy(); lid.parent = None; lid.matrix_world = lid_m   # the lid comes OFF
    gm = PR.skin_mat("gros michel", base="#E9C640", neck="#A9B23A")
    inside = []
    for k, (dx, dy, yaw) in enumerate(((-0.08, 0.03, 0.4), (0.09, -0.03, 2.7), (0.0, 0.05, -0.3))):
        r_, fs = PR.bunch(f"gros bunch {k}", (CX + dx, CY + dy, cr["inner_z"] + 0.01), gm, n=4, seed=60 + k, L=0.14, spread=0.6, parent=root)
        r_.rotation_euler = (0, 0, yaw); inside += fs
    T_LID0, T_LID1, T_ROT0, T_ROT1, T_TIP0, T_TIP1 = 0.3, 1.05, 1.25, 2.7, 3.5, 4.3
    L0 = Vector(lid.location); L1 = L0 + Vector((-0.1, -0.06, 0.08))      # up off the crate and to his right (screen left), below his chin
    for f in range(1, F(T_LID1) + 1):
        t = (f - 1) / FPS; lid.location = L0.lerp(L1, ease((t - T_LID0) / (T_LID1 - T_LID0))); lid.keyframe_insert("location", frame=f)
        lid.rotation_euler = (0, math.radians(-14) * ease((t - T_LID0) / (T_LID1 - T_LID0)), 0); lid.keyframe_insert("rotation_euler", frame=f)
    drop(lid, T_LID1 + 0.03, TOP - 0.02, kick=(-0.45, -0.08, 0.05), spin=(0.5, -3.0, 0.3), bounce=0.15)   # he lets go: it clatters down
    PR.rot(gm, T_ROT0, T_ROT1, to=1.0)
    for t, a_ in ((0.0, 0), (T_TIP0, 0), (T_TIP0 + 0.15, 6), (T_TIP1, 88), (T_TIP1 + 0.12, 84), (DUR, 86)):
        piv.rotation_euler = (0, math.radians(a_), 0); piv.keyframe_insert("rotation_euler", frame=F(t))
    rnd = random.Random(5)
    for i, fo in enumerate(inside):   # the dead fruit slides out of the open top and lands across the table
        drop(fo, T_TIP0 + 0.62 + 0.04 * i, TOP, kick=(rnd.uniform(0.3, 0.55), rnd.uniform(-0.18, 0.0), 0.08), spin=(rnd.uniform(-5, 5), 2, rnd.uniform(-5, 5)), bounce=0.2)
    data = load_data()
    DP = Vector((-0.04, -0.05, 0)); data.place(DP.x, DP.y, 0)
    sc.frame_set(1); bpy.context.view_layer.update()
    sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}
    lid_inv = lid_m.inverted()
    def lid_end(t, sx):           # the lid's two short ends, where his hands take it
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return lid.matrix_world @ lid_inv @ Vector((CX + sx * (CW / 2 - 0.03), CY, cz + CH + 0.02))
    def push_pt(t, dz):           # the crate's right top edge, where he pushes it over
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return piv.matrix_world @ (root.matrix_parent_inverse @ Vector((CX - CW / 2 - 0.01, CY + dz, cz + CH - 0.02)))
    for s_ in "LR":
        sx = -1 if sh[s_].x < DP.x else 1
        reach(data, s_, lambda t, sx=sx: lid_end(t, sx), T_LID0, T_LID1, elbow_out=0.5)
        reach(data, s_, lambda t, sx=sx: push_pt(t, 0.06 * sx), T_TIP0, T_TIP0 + 0.3, back=0.6, elbow_out=0.8)   # a shove, then it goes over on its own: following the edge up brings his arms into his face
    data.look_at((CX, CY, cz + 0.2), 0.15, max_yaw=30)
    data.look_at((CX, CY, cz), T_ROT0 + 0.3, max_yaw=30)
    data.look_at((0.0, -2.2, 0.7), T_ROT1 + 0.1, max_yaw=30)        # to us: see?
    data.look_at((CX + 0.35, CY - 0.15, TOP), T_TIP1 + 0.15, max_yaw=30)   # the fruit across the table
    data.idle(0.0, DUR)
    data.expression("happy", 0.2, T_ROT0)
    data.expression("worried", T_ROT0 + 0.3, DUR)
    data.blink(1.1); data.blink(T_ROT1 + 0.4); data.blink(DUR - 0.4)
    data.finish()
    soft_key("crate key", (0.55, -1.25, 0.95), (CX, CY, cz + 0.08), energy=30, size=26)
    C0, C1 = Vector((0.2, -1.45, 0.66)), Vector((0.2, -1.33, 0.62)); LK = Vector((0.2, -0.3, 0.46))   # centred between him and where the crate lands, so the spill is in frame
    cam = K.camera(tuple(C0), tuple(LK), lens=30, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, (CX, CY, cz + 0.1)))
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("old crate", "gros bunch"),
                conseq=[("the lid comes off and drops", lambda: meshes([lid]), T_LID0, T_LID1 + 0.6),
                        ("the fruit goes black", inside, T_ROT0, T_ROT1),
                        ("the crate goes over and the dead fruit spills", lambda: meshes([root]), T_TIP0 + 0.2, DUR)])


# ================================================================ SHOT 4: the new strain
def shot4():
    """NO CURE, IN THE SOIL FOR DECADES. A young banana plant in a planter on the floor beside him. The rot climbs its
    stem out of the soil and its leaves droop and brown one after another. He takes hold of a drooping leaf and lifts it
    back up; he lets go and it flops down, dead."""
    lanes, kiosks = produce_set()
    PX, PY = -0.06, -0.42
    pl = PR.planter("planter", (PX, PY, 0.0), w=0.32, d=0.26, h=0.2)
    pt = PR.plant("young plant", (PX, PY, pl["top_z"] - 0.02), height=0.36, n_leaves=5, seed=8)
    T_CLIMB0, T_CLIMB1 = 0.2, DUR * 0.7
    PR.rot(pt["stem_mat"], T_CLIMB0, T_CLIMB1, to=0.95)
    # the leaf that points at him is the one he lifts; the others wilt in turn
    data = load_data()
    DP = Vector((0.31, -0.32, 0)); data.place(DP.x, DP.y, -22)
    sc.frame_set(1); bpy.context.view_layer.update()
    to_him = math.atan2(DP.y - PY, DP.x - PX)
    lifted = min(range(len(pt["leaves"])), key=lambda k: abs(((pt["leaves"][k][0].rotation_euler.z - to_him) + math.pi) % (2 * math.pi) - math.pi))
    hz, hm = pt["leaves"][lifted]
    hz.rotation_euler = (0, math.radians(-5), to_him)
    others = [k for k in range(len(pt["leaves"])) if k != lifted]
    for i, k in enumerate(others):
        h_, m_ = pt["leaves"][k]; PR.wilt(h_, m_, 0.5 + 0.45 * i, 1.6 + 0.45 * i, droop_deg=36, to=0.5)   # yellowed and mottled, not black: dark drooped leaves closed into one brown shape; splayed down and out, a collapsed umbrella: hung straight down they closed round the stem into a brown pod
    T_G0, T_G1, T_LET = 1.6, 2.6, 3.5          # he takes the leaf, lifts it, lets go
    def pitch(t):
        if t < 0.9: return -5
        if t < T_G0: return -5 + 35 * ease((t - 0.9) / (T_G0 - 0.9))      # it sags toward him
        if t < T_G1: return 30 - 45 * ease((t - T_G0) / (T_G1 - T_G0))     # he lifts it back up
        if t < T_LET: return -15
        u = t - T_LET; return 62 - 77 * math.exp(-u / 0.12) * math.cos(u * 14) if u < 1.2 else 62   # it flops down and bounces once
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; hz.rotation_euler = (0, math.radians(pitch(t)), to_him); hz.keyframe_insert("rotation_euler", frame=f)
    PR.rot(hm, T_G0, T_LET + 0.6, to=0.75)
    side = near_hand(data, Vector((PX, PY, 0.5)))
    def tip(t):
        sc.frame_set(F(t)); bpy.context.view_layer.update()
        return hz.matrix_world @ Vector((0.2, 0, 0.12))
    reach(data, side, tip, T_G0, T_LET, lead=0.45, back=0.5, elbow_out=0.4)
    data.look_at((PX, PY, 0.35), 0.3, max_yaw=40)
    data.look_at((PX, PY, 0.5), T_G0, max_yaw=40)
    data.look_at((PX, PY, 0.3), T_LET + 0.3, max_yaw=40)
    data.look_at((DP.x - 0.3, -2.2, 0.7), DUR - 0.3, max_yaw=40)
    data.idle(0.0, DUR)
    data.expression("worried", 0.2, T_LET)
    data.expression("surprised", T_LET + 0.1, DUR)
    data.blink(0.8); data.blink(T_G1 + 0.2); data.blink(DUR - 0.4)
    data.finish()
    soft_key("plant key", (-0.75, -1.3, 1.0), (PX, PY, 0.45), energy=45, size=28)
    C0, C1 = Vector((0.12, -1.68, 0.54)), Vector((0.12, -1.56, 0.52)); LK = Vector((0.12, -0.35, 0.42))   # plant and him both whole in frame
    cam = K.camera(tuple(C0), tuple(LK), lens=26, fstop=4.0)
    camera_path(cam, lambda t: (C0.lerp(C1, ease(t / DUR)), LK, (PX, PY, 0.45)))
    leaves = [o for h_, _ in pt["leaves"] for o in h_.children]
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("young plant",),
                conseq=[("the rot climbs the stem", [pt["stem"]], T_CLIMB0, T_CLIMB1),
                        ("the leaves droop", leaves, 0.5, DUR),
                        ("the lifted leaf flops down", list(hz.children), T_LET, DUR)])


# ================================================================ SHOT 5: no banana to switch to
def shot5():
    """THE PAYOFF. The rail again, an ECUADOR banana box under its far end. The rot starts at the bunch over the box
    and comes down the row toward him; each bunch goes black and drops off its hook to the floor. He lifts the LAST
    yellow bunch off its hook and hugs it to his chest, looking at us, the camera pushing in to him. It ends there."""
    lanes, kiosks = produce_set()
    mats = [PR.skin_mat(f"rail {k}") for k in range(N_HOOK)]
    rows = rail_row(lambda k: mats[k])
    R = Matrix.Rotation(math.radians(RAIL_YAW), 3, 'Z')
    far = Vector((RAIL0[0], RAIL0[1], 0)) + R @ Vector((RAIL_LEN + 0.12, 0.16, 0))
    PR.produce_box("ecuador box", (far.x, far.y, 0.0), yaw=math.radians(RAIL_YAW - 90))
    T0_, STEP = 0.25, 0.5
    for i, k in enumerate(range(N_HOOK - 1, 0, -1)):        # from the far end toward him; the last one (k = 0) never rots
        tb = T0_ + STEP * i
        PR.rot(mats[k], tb, tb + 0.55, to=1.0, frm=0.1)
        p, sw, root, fingers = rows[k]
        PR.swing(sw, tb + 0.35, amp_deg=6, period=0.5, tau=0.3, nf=F(tb + 0.65))
        drop(root, tb + 0.65, 0.04, kick=(0.0, -0.08, 0.05), spin=(1.5, 0.5, 2.0), bounce=0.15)   # it lets go of the hook and lands
    T_REACH, T_LIFT, T_HUG = T0_ + STEP * (N_HOOK - 1) - 0.15, None, None
    T_LIFT = T_REACH + 0.45; T_HUG = T_LIFT + 0.5
    data = load_data()
    DP = RAIL_DP; data.place(DP.x, DP.y, RAIL_DROT)
    sc.frame_set(1); bpy.context.view_layer.update()
    last = rows[0]; lroot = last[2]
    sh = {s_: acts._shoulder(data, s_) for s_ in "LR"}; mid = (sh["L"] + sh["R"]) / 2
    sc.frame_set(1); bpy.context.view_layer.update(); hook_pose = lroot.matrix_world.copy()
    chest = mid + data.forward() * 0.17 + Vector((0, 0, -0.09))   # held to his chest, below the chin: his arms stay clear of his face and body
    # the last bunch leaves its hook in his hands and ends hugged to his chest (its own path, keyed every frame)
    M0 = hook_pose; lroot.parent = None; lroot.matrix_world = M0
    q0 = M0.to_quaternion(); from mathutils import Quaternion
    q1 = Quaternion((0, 0, 1), math.radians(14)) @ Quaternion((0, 1, 0), math.radians(-90)) @ Quaternion((1, 0, 0), math.radians(-12))
    lroot.rotation_mode = 'QUATERNION'
    def bpos(t):
        u = ease((t - T_LIFT) / (T_HUG - T_LIFT)); return M0.translation.lerp(chest, u)
    for f in range(1, NF + 1):
        t = (f - 1) / FPS; u = ease((t - T_LIFT) / (T_HUG - T_LIFT))
        lroot.location = bpos(t); lroot.keyframe_insert("location", frame=f)
        lroot.rotation_quaternion = q0.slerp(q1, u); lroot.keyframe_insert("rotation_quaternion", frame=f)
    for s_ in "LR":
        sx = -1 if sh[s_].x < mid.x else 1
        reach(data, s_, lambda t, sx=sx: bpos(t) + Vector((sx * 0.055, 0, -0.04)), T_LIFT, DUR, lead=T_LIFT - T_REACH, elbow_out=0.5)
    data.look_at(rows[N_HOOK - 1][0], 0.1, max_yaw=45)
    data.look_at(rows[3][0], T0_ + STEP * 2, max_yaw=45)
    data.look_at(rows[1][0], T0_ + STEP * 4 - 0.1, max_yaw=45)
    data.look_at(last[0], T_REACH, max_yaw=45)
    data.look_at((DP.x, -2.4, 0.75), T_HUG + 0.25, max_yaw=45)          # hugging it, to us
    data.idle(0.0, DUR)
    data.expression("worried", 0.2, DUR)
    data.blink(0.9); data.blink(T_HUG + 0.6)
    data.finish()
    soft_key("rail key", (0.9, -1.7, 1.1), (0.25, -0.62, 0.62), energy=40, size=34)
    soft_key("hug key", (-0.5, -1.6, 0.9), tuple(chest), energy=18, size=18)
    C0, LK0 = RAIL_C0, RAIL_LK
    C1, LK1 = Vector((DP.x + 0.05, DP.y - 0.85, 0.68)), Vector((DP.x + 0.02, DP.y, 0.58))
    cam = K.camera(tuple(C0), tuple(LK0), lens=26, fstop=3.5)
    camera_path(cam, lambda t: (C0.lerp(C1, ease((t - T_REACH + 0.6) / 2.2)), LK0.lerp(LK1, ease((t - T_REACH + 0.6) / 2.2)), DP + Vector((0, 0, 0.5))))
    fallen = [r[2] for r in rows[1:]]
    return dict(lanes=lanes, kiosks=list(kiosks.values()), data=data, rest=1, grips=("rail bunch 0",),
                conseq=[("the bunches go black and fall, toward him", lambda: meshes(fallen), T0_, T_REACH + 0.6),
                        ("he holds the last yellow bunch", lambda: meshes([lroot]), T_HUG, DUR)])


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}
