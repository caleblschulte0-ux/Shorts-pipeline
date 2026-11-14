"""The BODY check, for every 3D shot (caaleb, 2026-11-12: "Data looks really fucking weird here. He's bending in
inhuman ways. I shouldn't have to bring that type of shit up").

Every frame of the shot, MEASURED on the posed rig, never eyeballed:
  elbow   bends 0..ELBOW_MAX and never points forward (a backward-bending arm)
  knee    bends 0..KNEE_MAX and never points backward
  wrist   the hand turns off the forearm by at most WRIST_MAX
  shoulder the upper arm never swings more than BEHIND_MAX behind the body
  hand    never inside the torso
  head    bends off the chest (neck and head together) by at most HEAD_BEND_MAX: a look down bends the neck now
          (character.Data._tilt), and a look down on top of a slumped performance must still be a neck a body has
A shot with more than GRACE bad frames for any rule is refused before it renders, with the frames and the rule named.
"""
import math
import bpy
from mathutils import Vector

ELBOW_MAX = 150.0
KNEE_MAX = 140.0
WRIST_MAX = 80.0
BEHIND_MAX = 55.0
POINT_K = 0.35          # how far the joint must point the wrong way (share of its offset) to count
HAND_IN = 0.07          # metres from the torso axis: inside his coat
HEAD_BEND_MAX = 60.0    # degrees the head may tip off the chest's line, neck and head together (a person's neck flexes
                        # ~50-60 deg forward); a look down is at most 38 (character.Data.TILT_DOWN), a sad slump adds ~18
GRACE = 2               # frames


def _seg(M, pb):
    return M @ pb.head, M @ pb.tail


def _ang(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, u.normalized().dot(v.normalized())))))


def _off(a, joint, b):
    """the joint's offset from the straight line a-b (zero when the limb is straight)"""
    ab = b - a
    if ab.length < 1e-6: return Vector((0, 0, 0))
    t = (joint - a).dot(ab) / ab.length_squared
    return joint - (a + ab * t)


def check(data, nf, step=1, name="shot"):
    sc = bpy.context.scene; bad = {}; worst = {}
    def hit(rule, f, val):
        bad.setdefault(rule, []).append(f); worst[rule] = max(worst.get(rule, 0.0), val)
    for f in range(1, nf + 1, step):
        sc.frame_set(f); bpy.context.view_layer.update(); M = data.arm.matrix_world
        yaw = data.arm.rotation_euler.z; fw = Vector((math.sin(yaw), -math.cos(yaw), 0))
        s0, s1 = _seg(M, data.pb["spine"]); c0, c1 = _seg(M, data.pb["chest"])
        h0, h1 = _seg(M, data.pb["head"]); hb = _ang(c1 - c0, h1 - h0)
        if hb > HEAD_BEND_MAX: hit("head bent off the neck", f, hb)
        for s in "LR":
            sh, el = _seg(M, data.pb[f"arm.{s}"]); _, wr = _seg(M, data.pb[f"fore.{s}"]); _, hd = _seg(M, data.pb[f"hand.{s}"])
            bend = _ang(el - sh, wr - el)
            if bend > ELBOW_MAX: hit("elbow over-bent", f, bend)
            o = _off(sh, el, wr)
            if bend > 20 and o.length > 1e-4 and o.normalized().dot(fw) > POINT_K: hit("elbow bends backward", f, bend)
            wa = _ang(wr - el, hd - wr)
            if wa > WRIST_MAX: hit("wrist snapped", f, wa)
            u = (el - sh).normalized(); behind = math.degrees(math.asin(max(-1.0, min(1.0, -u.dot(fw)))))
            if behind > BEHIND_MAX: hit("arm behind the back", f, behind)
            for p in (wr, hd):           # inside the torso: near the spine/chest axis, between hip and shoulder
                a, b = s0, c1; ab = b - a; t = (p - a).dot(ab) / ab.length_squared
                if 0.1 < t < 0.95 and (p - (a + ab * t)).length < HAND_IN: hit("hand inside the body", f, (p - (a + ab * t)).length); break
            hp, kn = _seg(M, data.pb[f"leg.{s}"]); _, an = _seg(M, data.pb[f"shin.{s}"])
            kb = _ang(kn - hp, an - kn)
            if kb > KNEE_MAX: hit("knee over-bent", f, kb)
            o = _off(hp, kn, an)
            if kb > 15 and o.length > 1e-4 and o.normalized().dot(fw) < -POINT_K: hit("knee bends backward", f, kb)
    fails = {r: v for r, v in bad.items() if len(set(v)) > GRACE}
    if not bad: print(f"ANATOMY {name}: every joint inside a body's range on every frame -> OK", flush=True)
    for r, fr in sorted(bad.items()):
        fr = sorted(set(fr))
        print(f"ANATOMY {name}: {r} on {len(fr)} frames (worst {worst[r]:.0f}), frames {fr[:6]}{'...' if len(fr) > 6 else ''}"
              f" -> {'FAIL' if r in fails else 'within grace'}", flush=True)
    return not fails
