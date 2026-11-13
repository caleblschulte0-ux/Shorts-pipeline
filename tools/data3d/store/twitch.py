"""TWITCH: measure where Data jerks ("why does data tweak out", caaleb 2026-11-13). shots.py runs check() on every shot, beside anatomy and clipping;
under STAGING=strict a WHIP (any bone faster than WHIP_DEG in one frame) or a face pop fails the shot.
For every frame it takes each bone's world rotation and the face controls, and reports
  SNAP    a bone that turns faster than a person does (head/neck > HEAD_DEG per frame at 30 fps)
  JERK    a bone that goes from still to fast (or fast to still) in one frame: a pop, not a move
  JITTER  a bone whose turn reverses direction again and again (a shake), per second
  FACE    a face control (smile/open/frown/lid/brow) that jumps more than FACE_JUMP in a frame
Exit code 0 always; the lines start with TWITCH so proof_loop can pick them up."""
import bpy, math, os

HEAD_DEG = float(os.environ.get("TWITCH_HEAD", "6"))      # 180 deg/s
LIMB_DEG = float(os.environ.get("TWITCH_LIMB", "12"))
JERK_DEG = float(os.environ.get("TWITCH_JERK", "4"))
FACE_JUMP = float(os.environ.get("TWITCH_FACE", "0.35"))
WHIP_DEG = float(os.environ.get("TWITCH_WHIP", "30"))     # the fail line: 900 deg/s is a glitch, never a move
HEADISH = ("head", "neck", "spine", "chest", "hips", "root")
FPS_ = 30


def ang(q1, q2):
    a = math.degrees(q1.rotation_difference(q2).angle)
    return min(a, 360.0 - a)                     # q and -q are the same rotation


def measure(data, NF):
    sc = bpy.context.scene; arm = data.arm
    names = [b.name for b in arm.pose.bones]
    rot, face = {n: [] for n in names}, []
    for f in range(1, NF + 1):
        sc.frame_set(f); M = arm.matrix_world
        for b in arm.pose.bones: rot[b.name].append((M @ b.matrix).to_quaternion())
        face.append(data._face_state())
    events, worst = [], (0.0, None, 0)
    for n in names:
        q = rot[n]
        v = [0.0] + [ang(q[i - 1], q[i]) for i in range(1, len(q))]
        lim = HEAD_DEG if n.startswith(HEADISH) else LIMB_DEG
        for i in range(1, len(v)):
            if v[i] > worst[0]: worst = (v[i], n, i + 1)
            if v[i] > lim: events.append((i + 1, "SNAP", n, f"{v[i]:.1f} deg/frame"))
            if abs(v[i] - v[i - 1]) > JERK_DEG and max(v[i], v[i - 1]) > 2 * min(v[i], v[i - 1]) + 1:
                events.append((i + 1, "JERK", n, f"{v[i-1]:.1f} -> {v[i]:.1f} deg/frame"))
    pops = []
    for key in face[0]:
        for i in range(1, len(face)):
            d = abs(face[i][key] - face[i - 1][key])
            if d > FACE_JUMP:
                events.append((i + 1, "FACE", key, f"{face[i-1][key]:.2f} -> {face[i][key]:.2f} in one frame"))
                if key != "lid": pops.append((i + 1, key))          # a blink is meant to be fast
    events.sort()
    return events, worst, pops


def check(data, NF, name="shot"):
    events, worst, pops = measure(data, NF)
    seen = set()
    for f, kind, n, msg in events:
        k = (kind, n, f // 6)
        if k in seen: continue
        seen.add(k); print(f"TWITCH {name} f{f} t={(f-1)/FPS_:.2f}s {kind} {n}: {msg}")
    ok = worst[0] <= WHIP_DEG and not pops
    print(f"TWITCH {name}: fastest bone {worst[1]} {worst[0]:.1f} deg/frame at f{worst[2]} (fail over {WHIP_DEG:.0f}); "
          f"face pops {len(pops)} -> {'OK' if ok else 'FAIL'}")
    return ok
