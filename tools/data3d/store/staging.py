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

FPS = 24
BACK_DEG = 105      # face this far from the lens is the back of his head
BACK_S = 0.35       # a glance away is fine; a held back is not
MIN_H = 0.14        # of the frame height


def face_dir(data):
    pb = data.pb["head"]
    delta = pb.matrix @ pb.bone.matrix_local.inverted()
    return (data.arm.matrix_world.to_3x3() @ delta.to_3x3() @ Vector((0, -1, 0))).normalized()


def check(data, cam, nf, step=2, name="shot", cutaway=None):
    """cutaway=(t0, t1): a cut to a shot that is not on Data (the row from above); his staging is judged off it"""
    sc = bpy.context.scene; back_run = 0; worst = 0.0; worst_run = 0; small = 0; n = 0; hs = []
    for f in range(1, nf + 1, step):
        if cutaway and cutaway[0] <= (f - 1) / FPS < cutaway[1]: back_run = 0; continue
        sc.frame_set(f); bpy.context.view_layer.update()
        head = data.arm.matrix_world @ data.pb["head"].head
        to_cam = (cam.matrix_world.translation - head); to_cam.z = 0
        fd = face_dir(data); fd.z = 0
        ang = math.degrees(fd.angle(to_cam)) if fd.length > 1e-4 and to_cam.length > 1e-4 else 0.0
        worst = max(worst, ang)
        back_run = back_run + step if ang > BACK_DEG else 0; worst_run = max(worst_run, back_run)
        top = data.arm.matrix_world @ data.pb["head"].tail; foot = data.arm.matrix_world.translation
        a = world_to_camera_view(sc, cam, top); b = world_to_camera_view(sc, cam, foot)
        h = abs(a.y - b.y); hs.append(h); small += h < MIN_H; n += 1
    back_s = worst_run / FPS
    hs.sort(); med = hs[len(hs) // 2] if hs else 0
    ok = back_s <= BACK_S and small <= n * 0.5
    print(f"STAGING {name}: face-to-lens worst {worst:.0f} deg, back turned for {back_s:.2f}s (max {BACK_S}), "
          f"height in frame median {med:.2f} (min {MIN_H}) -> {'OK' if ok else 'FAIL'}", flush=True)
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
