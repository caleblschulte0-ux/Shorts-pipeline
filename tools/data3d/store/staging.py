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


CONSEQ_MIN_H = 0.035    # of the frame height: a consequence smaller than this is not seen on a phone
CONSEQ_SEEN = 0.6       # of its window it must be in frame and that big


def consequence(cam, nf, items, name="shot"):
    """EVERY ACTION SHOWS ITS CONSEQUENCE (caaleb 2026-11-12: "if this guy's pulling things off a calendar, maybe
    show them falling to the ground ... if this guy's pouring coins in a jar, show them falling ... give the emphasis
    to it"). A shot declares, for each thing Data does, what it CAUSES: [(label, [objects], t0, t1)]. Over t0..t1 the
    caused things must be inside the frame and at least CONSEQ_MIN_H of its height (the group's projected extent) for
    CONSEQ_SEEN of the time. A shot that declares nothing fails: an action with no shown result is the defect."""
    sc = bpy.context.scene; ok_all = bool(items)
    if not items: print(f"CONSEQUENCE {name}: no action declares what it causes -> FAIL", flush=True)
    for label, objs, t0, t1 in items:
        objs = objs() if callable(objs) else objs     # resolved now: the set dressing replaces objects after the shot is built
        seen = n = 0
        for f in range(int(round(t0 * FPS)) + 1, int(round(t1 * FPS)) + 2, 2):
            sc.frame_set(f); bpy.context.view_layer.update(); ys = []; xs = []
            for o in objs:
                if o.hide_render or (o.type == 'MESH' and max(abs(v) for v in o.matrix_world.to_scale()) < 1e-3): continue
                for c in o.bound_box:
                    p = world_to_camera_view(sc, cam, o.matrix_world @ Vector(c))
                    if p.z > 0 and -0.05 <= p.x <= 1.05 and -0.05 <= p.y <= 1.05: xs.append(p.x); ys.append(p.y)
            n += 1
            if ys and max(ys) - min(ys) >= CONSEQ_MIN_H: seen += 1
        frac = seen / max(1, n); good = frac >= CONSEQ_SEEN; ok_all &= good
        print(f"CONSEQUENCE {name}: {label}: on screen and big enough {frac:.0%} of its window (min {CONSEQ_SEEN:.0%}) -> {'OK' if good else 'FAIL'}", flush=True)
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
    live = [lab for lab, _, t0, t1 in items if t1 >= dur - END_S + 1e-3 and t0 <= dur - END_S * 0.5]
    def dist(f):
        sc.frame_set(f); bpy.context.view_layer.update()
        return (cam.matrix_world.translation - data.arm.matrix_world @ data.pb["head"].head).length
    mid, end = dist(max(1, nf // 2)), dist(nf)
    ok = bool(live) and end <= mid * PULL_BACK
    print(f"ENDING {name}: payoff still on screen in the last {END_S:.0f}s: {live or 'NOTHING'}; camera ends {end:.2f} m from him "
          f"vs {mid:.2f} m mid-shot (max x{PULL_BACK}) -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok
