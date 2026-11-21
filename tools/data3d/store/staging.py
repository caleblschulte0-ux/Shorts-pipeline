"""The filmmaker's check, for every 3D shot (caaleb, 2026-11-12: "There's some scenes where it's, like, backs turned
and it's, like, weird ... we're not properly utilizing / optimizing / showing Data in the right way").

MEASURED, not eyeballed: through the whole shot, which way is Data's FACE pointing relative to the camera, and how
big is he in the frame? A shot fails when his face is turned away from the lens (more than BACK_DEG) for longer
than BACK_S, or when he is smaller than MIN_H of the frame height for most of it. Run it before any render; a failed
shot is restaged, never shipped.
"""
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); from clock import FPS   # the one clock (tools/data3d/clock.py)
BACK_DEG = 105      # face this far from the lens is the back of his head
BACK_S = 0.35       # a glance away is fine; a held back is not
MIN_H = 0.28        # of the frame height, head to feet: a MEDIUM shot or closer (2026-11-12 brief: "Avoid wide shots
                    # where Data becomes tiny ... use medium shots and close-ups"; the first 3D short ran at 0.14 and
                    # its judges called him tiny at 6-9 s and 24-26 s). Cropped by a close-up he measures over 1.
SMALL_OK = 0.15     # of the shot he may be smaller than that (an establishing beat, a cutaway)
EDGE = 0.12         # his head's centre stays this far inside the frame's sides (a phone crops the edges of a Short, and a
                    # face cut by the frame edge is not a shot: the banana short's restaged rail put him half out of frame)
TOP_CUT = 0.985     # the crown of his head (the head bone's tail, under his ears) stays inside the top of the frame
HIDDEN_S = 0.3      # his FACE may be behind something (a prop swinging past) this long at a stretch, no longer. The banana
                    # short's first rail had a bunch hanging in front of his face for the whole beat, facing the lens,
                    # big in frame, and every number above passed it; this is the ray that sees it.


def _his(data):
    out, todo = set(), [data.arm]
    while todo:
        o = todo.pop(); out.add(o.name); todo.extend(o.children)
    return out


def face_hidden(data, cam, fd):
    """is his face behind something? Five rays from the lens to his face (centre, left, right, brow, chin); hidden when
    three or more stop on something that is not him."""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    h0 = data.arm.matrix_world @ data.pb["head"].head; h1 = data.arm.matrix_world @ data.pb["head"].tail
    r = (h1 - h0).length * 0.45; c = h0.lerp(h1, 0.5) + fd * r * 0.8
    side = fd.cross(Vector((0, 0, 1))); side = side.normalized() if side.length > 1e-4 else Vector((1, 0, 0))
    o = cam.matrix_world.translation; mine = _his(data); blocked = 0
    for p in (c, c + side * r * 0.5, c - side * r * 0.5, c + Vector((0, 0, r * 0.4)), c - Vector((0, 0, r * 0.4))):
        d = p - o; L = d.length
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d.normalized(), distance=L - 0.02)
        if hit and ob is not None and ob.name not in mine and ob.original.name not in mine:
            blocked += 1
    return blocked >= 3


def face_dir(data):
    pb = data.pb["head"]
    delta = pb.matrix @ pb.bone.matrix_local.inverted()
    return (data.arm.matrix_world.to_3x3() @ delta.to_3x3() @ Vector((0, -1, 0))).normalized()


def check(data, cam, nf, step=2, name="shot", cutaway=None, min_h=None):
    """cutaway=(t0, t1): a cut to a shot that is not on Data (the row from above); his staging is judged off it"""
    min_h = MIN_H if min_h is None else min_h
    sc = bpy.context.scene; back_run = 0; worst = 0.0; worst_run = 0; small = 0; n = 0; hs = []; hid_run = 0; hid_worst = 0; cut = 0
    for f in range(1, nf + 1, step):
        if cutaway and cutaway[0] <= (f - 1) / FPS < cutaway[1]: back_run = 0; continue
        sc.frame_set(f); bpy.context.view_layer.update()
        head = data.arm.matrix_world @ data.pb["head"].head
        to_cam = (cam.matrix_world.translation - head); to_cam.z = 0
        fd = face_dir(data)
        hid_run = hid_run + step if face_hidden(data, cam, fd) else 0; hid_worst = max(hid_worst, hid_run)
        fd.z = 0
        ang = math.degrees(fd.angle(to_cam)) if fd.length > 1e-4 and to_cam.length > 1e-4 else 0.0
        worst = max(worst, ang)
        back_run = back_run + step if ang > BACK_DEG else 0; worst_run = max(worst_run, back_run)
        top = data.arm.matrix_world @ data.pb["head"].tail; foot = data.arm.matrix_world.translation
        a = world_to_camera_view(sc, cam, top); b = world_to_camera_view(sc, cam, foot)
        h = abs(a.y - b.y); hs.append(h); small += h < min_h; n += 1
        c = world_to_camera_view(sc, cam, (data.arm.matrix_world @ data.pb["head"].head).lerp(top, 0.5))
        cut += not (EDGE <= c.x <= 1 - EDGE and EDGE * 0.5 <= c.y <= 1 - EDGE * 0.5) or a.y > TOP_CUT   # the top of his head off the frame
    back_s = worst_run / FPS
    hs.sort(); med = hs[len(hs) // 2] if hs else 0
    hid_s = hid_worst / FPS
    ok = back_s <= BACK_S and small <= n * SMALL_OK and hid_s <= HIDDEN_S and cut <= n * SMALL_OK
    print(f"STAGING {name}: face-to-lens worst {worst:.0f} deg, back turned for {back_s:.2f}s (max {BACK_S}), "
          f"face behind something for {hid_s:.2f}s (max {HIDDEN_S}), head at the frame edge on {cut / max(1, n):.0%} of frames (max {SMALL_OK:.0%}), "
          f"height in frame median {med:.2f}, under {min_h} on {small / max(1, n):.0%} of frames (max {SMALL_OK:.0%}) -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok


def framing(data, cam, nf, step=4):
    """the shot's FRAMING fingerprint, medians over the shot (store/variety.py compares it across beats): where his head
    centre sits in the frame (x, y as fractions), how tall he is (head to feet, as staging.check), which side of him the
    lens sees (yaw, degrees: 0 his face, +-90 a profile, signed) and from how high (pitch, degrees above his head)"""
    sc = bpy.context.scene; xs, ys, hs, yaws, pits = [], [], [], [], []
    for f in range(1, nf + 1, step):
        sc.frame_set(f); bpy.context.view_layer.update()
        h0 = data.arm.matrix_world @ data.pb["head"].head; top = data.arm.matrix_world @ data.pb["head"].tail
        foot = data.arm.matrix_world.translation
        c = world_to_camera_view(sc, cam, h0.lerp(top, 0.5)); a = world_to_camera_view(sc, cam, top); b = world_to_camera_view(sc, cam, foot)
        xs.append(c.x); ys.append(c.y); hs.append(abs(a.y - b.y))
        to_cam = cam.matrix_world.translation - h0
        fd = face_dir(data); fd.z = 0; flat = to_cam.copy(); flat.z = 0
        if fd.length > 1e-4 and flat.length > 1e-4:
            yaw = math.degrees(math.atan2(fd.x * flat.y - fd.y * flat.x, fd.dot(flat) / 1.0))
            yaws.append(yaw)
        pits.append(math.degrees(math.atan2(to_cam.z, max(1e-6, flat.length))))
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    return dict(x=round(med(xs), 3), y=round(med(ys), 3), h=round(med(hs), 3), yaw=round(med(yaws), 1), pitch=round(med(pits), 1),
                lens=round(cam.data.lens, 1))


CONSEQ_MIN_H = 0.12     # of the frame height: a consequence smaller than this is not seen on a phone. It was 0.035
                        # until 2026-11-13, when every saffron shot passed it and then failed the judge with the idea's
                        # prop "a few pixels on a phone" (threads, a scale needle, a balance beam) -- 40 minutes of
                        # proof renders to learn what this check should have said in seconds (caaleb: "Why don't we
                        # fix these things beforehand?")
CONSEQ_INSIDE = 0.85    # of the group's bounding-box corners inside the frame: a pan cut by the frame edge is not seen
CONSEQ_SEEN = 0.6       # of its window it must be in frame, whole and that big
HERO_MIN_H = 0.25       # of the frame height: THE BEAT'S OWN PROP (the shot's first consequence, or the one marked
                        # {"hero": True}) must be at least this big at the median of its window. 2026-11-18, card
                        # rewards: every shot passed the 12% floor and the judge still scored them 40-60 because the
                        # idea's prop (a coin tray, price tags, a ramp) was a sliver beside Data's head on a phone.
                        # A quarter of the frame is what the one passing shot (the tipped piggy bank) had.
FLOOR_Z = -0.05         # metres: a consequence object whose whole box is below this is built under the set (a kit
                        # part parented wrongly lands at the world origin under the counter: card_kit's chute and
                        # lever on 2026-11-18, invisible for three rounds with every check green)


MOVE_MIN = 0.06         # of the frame height (115 px of a 1080x1920 Short): the least a MOVING part must travel on screen
                        # for its move to be seen on a phone. 2026-11-14: saffron's gram-scale needle passed every size
                        # check (the whole scale was big) while the needle itself flicked ~2% of the frame height, and
                        # the judge failed it as "the needle hardly moves" -- the move was the point and nothing measured
                        # it. Three times that is the floor: about a centimetre on a phone held in the hand.


def _corners(o, dg):
    oe = o.evaluated_get(dg); M = oe.matrix_world
    return [M @ Vector(c) for c in oe.bound_box]


def motion_px(ref, now, project, res):
    """the farthest any tracked point has moved on screen from where it was at the start of the window, in pixels.
    ref / now: {key: [world points]} at the window's start and now; project(p) -> (x, y, depth) in 0..1 of the frame,
    BOTH projected through the camera as it is NOW, so a camera move is not counted as the thing moving."""
    best = 0.0
    for k, pts in now.items():
        for a, b in zip(ref.get(k, ()), pts):
            pa, pb = project(a), project(b)
            if pa[2] <= 0 or pb[2] <= 0: continue
            best = max(best, ((pb[0] - pa[0]) * res[0]) ** 2 + ((pb[1] - pa[1]) * res[1]) ** 2)
    return best ** 0.5


def _hero_of(items):
    """the beat's own prop: the item marked {"hero": True}, else the first one"""
    for it in items:
        if len(it) > 4 and it[4].get("hero"): return it
    return items[0] if items else None


def consequence(cam, nf, items, name="shot"):
    """EVERY ACTION SHOWS ITS CONSEQUENCE (caaleb 2026-11-12: "if this guy's pulling things off a calendar, maybe
    show them falling to the ground ... if this guy's pouring coins in a jar, show them falling ... give the emphasis
    to it"). A shot declares, for each thing Data does, what it CAUSES: [(label, [objects], t0, t1)] (a 5th element {"whole": False}
    for a field-wide effect that runs past the frame). Over t0..t1 the caused things must be inside the frame, not cut
    by its edge (CONSEQ_INSIDE of their box corners), and at least CONSEQ_MIN_H of its height (the group's projected
    extent) for CONSEQ_SEEN of the time. A shot that declares nothing fails: an action with no shown result is the defect.
    The 5th element may also say what MOVES: {"moves": True} (the listed objects are the moving part) or
    {"moves": [objects] | callable} (the moving part inside a bigger group: a needle on a scale). That part's projected
    motion is MEASURED at the output resolution over the window and must reach MOVE_MIN of the frame height."""
    sc = bpy.context.scene; ok_all = bool(items)
    res = (sc.render.resolution_x, sc.render.resolution_y)
    if not items: print(f"CONSEQUENCE {name}: no action declares what it causes -> FAIL", flush=True)
    for it in items:
        label, objs, t0, t1 = it[:4]
        opt = it[4] if len(it) > 4 else {}
        whole = opt.get("whole", True)     # False: a field-wide effect that runs past the frame
        objs = objs() if callable(objs) else objs     # resolved now: the set dressing replaces objects after the shot is built
        hero = opt.get("hero", it is _hero_of(items)) and whole
        buried = [o.name for o in objs if o.type == 'MESH' and not o.hide_render
                  and max((o.matrix_world @ Vector(c)).z for c in o.bound_box) < FLOOR_Z]
        mv = opt.get("moves")
        if mv is True: mv = objs
        elif callable(mv): mv = mv()
        mv = [o for o in (mv or []) if o.type in ('MESH', 'FONT', 'CURVE')] if mv is not None else None
        ref = None; moved = 0.0
        seen = n = 0; hs = []
        for f in range(int(round(t0 * FPS)) + 1, int(round(t1 * FPS)) + 2, 2):
            sc.frame_set(f); bpy.context.view_layer.update(); ys = []; xs = []; tot = inside = 0
            if mv is not None:
                dg = bpy.context.evaluated_depsgraph_get()
                now = {o.name: _corners(o, dg) for o in mv if not o.hide_render}
                if ref is None: ref = now
                moved = max(moved, motion_px(ref, now, lambda p: world_to_camera_view(sc, cam, p), res))
            for o in objs:
                if o.hide_render or (o.type == 'MESH' and max(abs(v) for v in o.matrix_world.to_scale()) < 1e-3): continue
                for c in o.bound_box:
                    p = world_to_camera_view(sc, cam, o.matrix_world @ Vector(c))
                    if p.z <= 0: continue
                    tot += 1
                    if -0.01 <= p.x <= 1.01 and -0.01 <= p.y <= 1.01: inside += 1
                    if -0.05 <= p.x <= 1.05 and -0.05 <= p.y <= 1.05: xs.append(p.x); ys.append(p.y)
            n += 1; h = (max(ys) - min(ys)) if ys else 0.0; hs.append(h)
            if h >= CONSEQ_MIN_H and (not whole or inside >= CONSEQ_INSIDE * max(1, tot)): seen += 1
        frac = seen / max(1, n); good = frac >= CONSEQ_SEEN
        med = sorted(hs)[len(hs) // 2] if hs else 0.0
        extra = ""
        if hero:
            big = med >= HERO_MIN_H; good &= big
            extra += f"; THE BEAT'S PROP: median {med:.0%} of the frame (min {HERO_MIN_H:.0%}){'' if big else ': TOO SMALL BESIDE DATA ON A PHONE'}"
        if buried:
            good = False; extra += f"; built UNDER THE SET (whole box below the floor): {', '.join(buried[:4])}"
        motion = ""
        if mv is not None:
            if not mv: good = False; motion = "; it declares a moving part but names nothing that can move"
            else:
                big = moved >= MOVE_MIN * res[1]; good &= big
                motion = (f"; the moving part travels {moved:.0f} px on screen ({moved / res[1]:.1%} of the frame height, "
                          f"min {MOVE_MIN:.0%}){'' if big else ': TOO SMALL TO SEE MOVE'}")
        ok_all &= good
        print(f"CONSEQUENCE {name}: {label}: in frame, whole and big enough {frac:.0%} of its window (min {CONSEQ_SEEN:.0%}; "
              f"median height {med:.0%} of frame, min {CONSEQ_MIN_H:.0%}){motion}{extra} -> {'OK' if good else 'FAIL'}", flush=True)
    return ok_all


END_S = 1.0           # the last second of the video
PULL_BACK = 1.15      # the camera may end at most this much farther from him than it was mid-shot


def ending(data, cam, nf, items, name="shot"):
    """THE VIDEO ENDS ON ITS PAYOFF (2026-11-12 brief: "Create a satisfying visual payoff at the end instead of
    zooming out"; the first 3D short's showrunner hold: "the last 6 seconds are Data standing idle with no payoff").
    Run on the LAST shot only. Two things are measured: at least one declared consequence is still happening in the
    final END_S, and the camera does not pull back: its distance to his head at the last frame is at most PULL_BACK
    times what it was halfway through the shot."""
    sc = bpy.context.scene; dur = (nf - 1) / FPS
    live = [lab for lab, _, t0, t1 in (it[:4] for it in items) if t1 >= dur - END_S + 1e-3 and t0 <= dur - END_S * 0.5]   # a 5th element (options) is allowed
    def dist(f):
        sc.frame_set(f); bpy.context.view_layer.update()
        return (cam.matrix_world.translation - data.arm.matrix_world @ data.pb["head"].head).length
    mid, end = dist(max(1, nf // 2)), dist(nf)
    ok = bool(live) and end <= mid * PULL_BACK
    print(f"ENDING {name}: payoff still on screen in the last {END_S:.0f}s: {live or 'NOTHING'}; camera ends {end:.2f} m from him "
          f"vs {mid:.2f} m mid-shot (max x{PULL_BACK}) -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok


def _hide_curve(o):
    """the hide_render f-curve of an object (Blender 5 layered actions), or None"""
    ad = getattr(o, "animation_data", None)
    if not ad or not ad.action: return None
    for ly in getattr(ad.action, "layers", ()):
        for st in ly.strips:
            cb = st.channelbag(ad.action_slot) if ad.action_slot else None
            for fc in (cb.fcurves if cb else ()):
                if fc.data_path == "hide_render": return fc
    for fc in getattr(ad.action, "fcurves", ()):   # a legacy action
        if fc.data_path == "hide_render": return fc
    return None


def _hit(r, core):
    """where a bolt strikes, in the world: storm_kit.bolt tags its root ("hit"); a bolt a shot builds its own way (the
    ridge's s1_bolt keeps only the "parts" contract) strikes at the lowest point of its core"""
    if "hit" in r.keys(): return r.matrix_world @ Vector(r["hit"])
    if core.type == 'CURVE' and core.data.splines:
        return min((core.matrix_world @ Vector(p.co[:3]) for sp in core.data.splines for p in sp.points), key=lambda v: v.z)
    return core.matrix_world.translation.copy()


def strikes(nf):
    """every lightning bolt of the shot (anything with storm_kit's root["parts"] contract) and the frame each flash of
    it STARTS: [(root, frame)]. Read from the bolt's own hide_render keys, so a shot that flashes it its own way (the
    tower's longer stroke) is measured too"""
    out = []
    for r in bpy.data.objects:
        if "parts" not in r.keys(): continue
        core = bpy.data.objects.get(r["parts"][0])
        if core is None: continue
        fc = _hide_curve(core)
        vis = [f for f in range(1, nf + 1) if (fc.evaluate(f) < 0.5 if fc else not core.hide_render)]
        out += [(r, f) for i, f in enumerate(vis) if i == 0 or vis[i - 1] < f - 6]   # a return stroke's flicker is one strike
    return out


def near_strikes(data, nf, cutaway=None):
    """the strikes of this beat's event: [(root, start frame)] of every strike (strikes()) that lands within
    motion.SCENERY_M of him, off any cutaway. The storm's far bolts over the valley are scenery and not in it"""
    import motion as MO
    sc = bpy.context.scene; out = []
    for r, f in strikes(nf):
        if cutaway and cutaway[0] <= (f - 1) / FPS < cutaway[1]: continue
        sc.frame_set(f); bpy.context.view_layer.update()
        if (_hit(r, bpy.data.objects[r["parts"][0]]) - data.arm.matrix_world.translation).length <= MO.SCENERY_M:
            out.append((r, f))
    return out


def _flash(r, f, nf):
    """the frames of the flash that starts at f (while its core is shown), at most 0.3 s of them"""
    core = bpy.data.objects[r["parts"][0]]; fc = _hide_curve(core); out = []
    for g in range(f, min(nf, f + int(0.3 * FPS)) + 1):
        if (fc.evaluate(g) < 0.5) if fc else not core.hide_render: out.append(g)
        else: break
    return out or [f]


def _through_him(o, d, length, mine):
    """does the ray o + t*d (0 < t < length) pass through him? Whatever else it meets first is passed through"""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get(); pos = o.copy(); gone = 0.0
    for _ in range(24):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, pos, d, distance=max(1e-4, length - gone))
        if not hit: return False
        if ob is not None and (ob.name in mine or ob.original.name in mine): return True
        step = (loc - pos).length + 0.004; gone += step; pos = pos + d * step
        if gone >= length: return False
    return False


RINGS = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12)   # frame heights round a strike's target point


def bolt_view(data, cam, r, f, mine=None):
    """what the viewer sees one strike do at frame f, for motion.bolt_problems: (path, flags, ring, tilt, target_seen),
    or None for a bolt with no curve channel"""
    import math as _mt
    core = bpy.data.objects[r["parts"][0]]
    if core.type != 'CURVE' or not core.data.splines: return None
    sc = bpy.context.scene; sc.frame_set(f); bpy.context.view_layer.update()
    mine = mine or _his(data)
    C = cam.matrix_world.translation.copy(); cm = cam.matrix_world.to_3x3()
    world = [core.matrix_world @ Vector(p.co[:3]) for p in core.data.splines[0].points]
    hit = _hit(r, core)
    if (world[-1] - hit).length > (world[0] - hit).length: world.reverse()     # cloud first, target last
    world[-1] = hit
    path = []
    for p in world:
        q = world_to_camera_view(sc, cam, p); path.append((q.x, q.y) if q.z > 0 else None)
    flags = []
    for p in world:
        d = p - C; L = d.length; dn = d.normalized()
        flags.append("h" if _through_him(C, dn, L - 0.02, mine) else ("f" if _through_him(p + dn * 0.02, dn, 3.0, mine) else ""))
    vf = list(cam.data.view_frame(scene=sc)); fh = max(v.y / -v.z for v in vf) - min(v.y / -v.z for v in vf)
    dep = (hit - C).dot(cm @ Vector((0, 0, -1))); rx = cm @ Vector((1, 0, 0)); ry = cm @ Vector((0, 1, 0)); ring = None
    for rho in RINGS:
        if any(_through_him(C, (q - C).normalized(), (q - C).length + 3.0, mine)
               for q in (hit + (rx * _mt.cos(a) + ry * _mt.sin(a)) * rho * dep * fh for a in (6.2832 * k / 16 for k in range(16)))):
            ring = rho; break
    ins = [q is not None and 0 <= q[0] <= 1 and 0 <= q[1] <= 1 for q in path]
    e = ins.index(True) if True in ins else 0
    v = world[-1] - world[e]
    tilt = _mt.degrees(_mt.atan2(_mt.hypot(v.x, v.y), -v.z)) if v.length > 1e-6 else 0.0
    seen = None
    tg = r.get("target") if "target" in r.keys() else None
    if tg:
        objs = [bpy.data.objects[n] for n in ([tg] if isinstance(tg, str) else list(tg)) if n in bpy.data.objects]
        seen = False
        for o in objs:
            cs = [o.matrix_world @ Vector(c) for c in o.bound_box]; c = sum(cs, Vector()) / 8
            q = world_to_camera_view(sc, cam, c)
            if q.z > 0 and 0 <= q.x <= 1 and 0 <= q.y <= 1 and not _through_him(C, (c - C).normalized(), (c - C).length - 0.02, mine):
                seen = True
    return path, flags, ring, tilt, seen


def on_him(data, r, f):
    """does the strike starting at f land on him (within motion.TARGET_R of any of his bones)?"""
    import motion as MO
    sc = bpy.context.scene; sc.frame_set(f); bpy.context.view_layer.update(); M = data.arm.matrix_world
    hit = _hit(r, bpy.data.objects[r["parts"][0]])
    return min((hit - M @ v).length for b in data.arm.pose.bones for v in (b.head, b.tail)) <= MO.TARGET_R


def far(data, cam, nf, arc=(), name="shot", cutaway=None):
    """FAR (store/motion.py has the rules and their calibration): at each arc moment (fractions of the shot) Data is
    big; every strike lands near him, inside the frame, thick enough to read; a drop is seen from the side; and BOLT:
    every strike near him is seen whole, from where it enters the frame to its target, steep, and clear of his body
    unless he is its target (motion.bolt_problems, measured by bolt_view on every frame of its flash)"""
    import motion as MO
    sc = bpy.context.scene; res = (sc.render.resolution_x, sc.render.resolution_y); asp = res[0] / res[1]
    dur = nf / FPS; probs = []
    off = lambda f: bool(cutaway) and cutaway[0] <= (f - 1) / FPS < cutaway[1]
    def size(f):
        sc.frame_set(f); bpy.context.view_layer.update()
        hc = data.arm.matrix_world @ data.pb["head"].head; up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
        return abs(world_to_camera_view(sc, cam, hc + up * MO.STAND).y - world_to_camera_view(sc, cam, hc).y)
    sizes = []
    for at in arc:
        f = min(nf, max(1, int(round(at * dur * FPS)) + 1))
        if off(f): continue
        h = size(f); sizes.append(round(h, 2))
        if h < MO.FAR_H: probs.append(f"at {at:.2f} of the beat (f{f}) he is {h:.3f} of the frame height (min {MO.FAR_H})")
    n_st = 0
    for r, f in strikes(nf):
        if off(f): continue
        sc.frame_set(f); bpy.context.view_layer.update(); M = data.arm.matrix_world
        hit = _hit(r, bpy.data.objects[r["parts"][0]])
        if (hit - M.translation).length > MO.SCENERY_M: continue          # the storm's scenery, not this beat's event
        n_st += 1
        p = world_to_camera_view(sc, cam, hit)
        glow = max(bpy.data.objects[n].data.bevel_depth for n in r["parts"] if n in bpy.data.objects)
        q = world_to_camera_view(sc, cam, hit + (cam.matrix_world.to_3x3() @ Vector((1, 0, 0))) * glow)
        pts = [world_to_camera_view(sc, cam, M @ v) for b in data.arm.pose.bones for v in (b.head, b.tail)]
        gap = min((math.hypot((c.x - p.x) * asp, c.y - p.y) for c in pts if c.z > 0), default=9.9)
        for pr in MO.strike_problems(p, gap, abs(q.x - p.x) * res[0]):
            probs.append(f"{r.name} at f{f} {pr}")
    mine = _his(data); n_bolt = 0
    for r, f in near_strikes(data, nf, cutaway):          # BOLT (store/motion.py): what the viewer sees each strike do
        him = on_him(data, r, f); seen = []
        for g in _flash(r, f, nf):
            v = bolt_view(data, cam, r, g, mine)
            if v is None: break
            path, flags, ring, tilt, tseen = v
            for pr in MO.bolt_problems(path, flags, ring, him, tilt, tseen):
                if pr not in seen: seen.append(pr); probs.append(f"BOLT {r.name} at f{g} {pr}")
        n_bolt += 1
    hh, side = [], []
    for f in range(1, nf + 1):
        sc.frame_set(f); M = data.arm.matrix_world; pb = data.pb
        z = lambda b, t: (M @ (pb[b].tail if t else pb[b].head)).z
        hh.append(z("head", 1) - min(z("foot.L", 1), z("foot.R", 1), z("root", 0)))
        lat = (M @ pb["leg.L"].head) - (M @ pb["leg.R"].head); to = cam.matrix_world.translation - (M @ pb["head"].head)
        lat.z = 0; to.z = 0
        side.append(math.degrees(math.asin(min(1.0, abs(lat.normalized().dot(to.normalized()))))) if lat.length > 1e-6 and to.length > 1e-6 else 90.0)
    dr = [d for d in MO.drops(hh, side, fps=FPS) if not off(d[0])]
    if dr:
        probs.append(f"he drops (a knockdown, a sit, a crouch) at f{dr[0][0]}-{dr[-1][0]} seen {min(d[2] for d in dr):.0f} deg off his "
                     f"front (min {MO.DROP_SIDE:.0f}): from the front a fall reads as a hop; turn the lens to his side or three-quarter")
    ok = not probs
    print(f"FAR {name}: his size at the arc moments {sizes} (min {MO.FAR_H}); {n_st} strikes near him measured; "
          f"{n_bolt} strikes' channels seen (BOLT: in frame to the target, steep, off his body unless he is the target)"
          + "".join(f"; {p}" for p in probs[:8]) + f" -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok
