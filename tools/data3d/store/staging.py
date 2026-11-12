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


def check(data, cam, nf, step=2, name="shot"):
    sc = bpy.context.scene; back_run = 0; worst = 0.0; worst_run = 0; small = 0; n = 0; hs = []
    for f in range(1, nf + 1, step):
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
