"""TWITCH: measure where Data jerks ("why does data tweak out", caaleb 2026-11-13). shots.py runs check() on every shot, beside anatomy and clipping;
under STAGING=strict a WHIP (any bone faster than WHIP_DEG in one frame) or a face pop fails the shot.
For every frame it takes each bone's world rotation and the face controls, and reports
  SNAP    a bone that turns faster than a person does (head/neck > HEAD_DEG per frame at 30 fps)
  JERK    a bone that goes from still to fast (or fast to still) in one frame: a pop, not a move
  JITTER  a bone whose turn reverses direction again and again (a shake), per second
  FACE    a face control (smile/open/frown/lid/brow) that jumps more than FACE_JUMP in a frame
  FLUID   the arms: fastest turn, sharpest change of speed, stutters (a move that all but stops, then goes on), and
          how far each hand's travel to a job strays from a straight line (a wing swing)
  REACH   a hand short of the job it was given: the target was out of reach, the arm locks out straight to the side.
          This was the saffron short's "wing" (caaleb 2026-11-14, "his arms will bend goofy"): the second cash brick
          started 0.36 m to his right, the arm stretched straight out sideways after it
Exit code 0 always; the lines start with TWITCH so proof_loop can pick them up."""
import bpy, math, os

HEAD_DEG = float(os.environ.get("TWITCH_HEAD", "6"))      # 180 deg/s
LIMB_DEG = float(os.environ.get("TWITCH_LIMB", "12"))
JERK_DEG = float(os.environ.get("TWITCH_JERK", "4"))
FACE_JUMP = float(os.environ.get("TWITCH_FACE", "0.35"))
WHIP_DEG = float(os.environ.get("TWITCH_WHIP", "30"))     # the fail line: 900 deg/s is a glitch, never a move
# FLUID (caaleb 2026-11-14: "sometimes data's movements are not the best or most fluid"). An arm may be fast, but it
# speeds up and slows down like an arm: measured on the posted saffron short, arms went 0 -> 29 deg/frame inside a
# few frames (a prop the hand carried was moved too fast by the story) and stuttered 37 times in five shots.
ARM_FAST = float(os.environ.get("FLUID_FAST", "22"))      # deg/frame (660 deg/s)
ARM_ACC = float(os.environ.get("FLUID_ACC", "6"))         # deg/frame^2
ARM = ("arm.", "fore.", "hand.")
SHORT_MAX = 0.03        # m a hand on a job may fall short of it (the IK clamps a target out of reach: arm locked straight)
SHORT_GRACE = 2         # frames
BULGE_MAX = float(os.environ.get("FLUID_BULGE", "0.08"))   # m a hand's travel to a job may stray off its straight line
# (caaleb 2026-11-14: "his arms will bend goofy": the saffron short's wing swing to the money stack)
HEADISH = ("head", "neck", "spine", "chest", "hips", "root")
FPS_ = 30


def ang(q1, q2):
    a = math.degrees(q1.rotation_difference(q2).angle)
    return min(a, 360.0 - a)                     # q and -q are the same rotation


def measure(data, NF):
    sc = bpy.context.scene; arm = data.arm
    names = [b.name for b in arm.pose.bones]
    rot, face = {n: [] for n in names}, []
    wrist = {s: [] for s in "LR"}; shoulder = {s: [] for s in "LR"}
    for f in range(1, NF + 1):
        sc.frame_set(f); M = arm.matrix_world
        for b in arm.pose.bones: rot[b.name].append((M @ b.matrix).to_quaternion())
        for s_ in "LR":
            wrist[s_].append((M @ arm.pose.bones[f"fore.{s_}"].tail).copy()); shoulder[s_].append((M @ arm.pose.bones[f"arm.{s_}"].head).copy())
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
                blinking = any(abs(face[j]["lid"] - face[j - 1]["lid"]) > FACE_JUMP for j in range(max(1, i - 4), min(len(face), i + 5)))
                if key != "lid" and not (key == "squint" and blinking):   # a blink is meant to be fast, and squint is
                    pops.append((i + 1, key))       # read from the lower lid, which a blink moves too (life pass, 11-14)
    events.sort()
    fl = {"fast": (0.0, None, 0), "acc": (0.0, None, 0), "hitch": []}
    for n in names:
        if not n.startswith(ARM): continue
        q = rot[n]; v = [0.0] + [ang(q[i - 1], q[i]) for i in range(1, len(q))]
        for i in range(1, len(v)):
            if v[i] > fl["fast"][0]: fl["fast"] = (v[i], n, i + 1)
            a = abs(v[i] - v[i - 1])
            if i > 1 and a > fl["acc"][0]: fl["acc"] = (a, n, i + 1)
        for i in range(2, len(v) - 3):
            if v[i - 1] > 1.5 and v[i] < 0.3 * v[i - 1] and max(v[i + 1:i + 4]) > 1.5: fl["hitch"].append((i + 1, n))
    fl["bulge"] = (0.0, None, 0, 0)
    for side, fa, fb in getattr(data, "_approaches", []):
        fa, fb = max(1, fa), min(NF, fb)
        if fb - fa < 2: continue
        d = bulge([wrist[side][f - 1] - shoulder[side][f - 1] for f in range(fa, fb + 1)])   # in his frame: a hand that
        # comes down with him as he lands is on its line; the world sees his whole body's move as the hand's bulge
        if d > fl["bulge"][0]: fl["bulge"] = (d, side, fa, fb)
    short = []
    for (side, f), (tgt, _eo, _e0) in getattr(data, "_ik_keys", {}).items():
        if 1 <= f <= NF:
            miss = (wrist[side][f - 1] - tgt).length
            if miss > SHORT_MAX: short.append((miss, side, f))
    fl["short"] = sorted(short, reverse=True)
    measure.fluid = fl
    return events, worst, pops


def bulge(pts):
    """the farthest a hand's travel strays from the straight line between where it started and where it arrived
    (metres). A hand goes to a thing on a near-straight line; a wing swing strays 15-25 cm."""
    a, b = pts[0], pts[-1]; ab = b - a; L2 = ab.dot(ab)
    best = 0.0
    for p in pts[1:-1]:
        u = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
        best = max(best, (p - (a + ab * u)).length)
    return best


def check(data, NF, name="shot"):
    events, worst, pops = measure(data, NF)
    seen = set()
    for f, kind, n, msg in events:
        k = (kind, n, f // 6)
        if k in seen: continue
        seen.add(k); print(f"TWITCH {name} f{f} t={(f-1)/FPS_:.2f}s {kind} {n}: {msg}")
    fl = measure.fluid
    fluid_ok = fl["fast"][0] <= ARM_FAST and fl["acc"][0] <= ARM_ACC and not fl["hitch"] and fl["bulge"][0] <= BULGE_MAX
    sh = fl["short"]
    reach_ok = len(sh) <= SHORT_GRACE
    print(f"REACH {name}: hand short of its job by more than {SHORT_MAX * 100:.0f} cm on {len(sh)} frames"
          + (f" (worst {sh[0][0] * 100:.1f} cm, {sh[0][1]} f{sh[0][2]}; frames {sorted(f for *_, f in sh)[:8]})" if sh else "")
          + f" -> {'OK' if reach_ok else 'FAIL: the job is out of his reach, so the arm locks out straight (a wing); move it within about 0.18 m of his shoulder'}")
    print(f"FLUID {name}: fastest arm {fl['fast'][1]} {fl['fast'][0]:.1f} deg/frame at f{fl['fast'][2]} (max {ARM_FAST:.0f}), "
          f"sharpest change {fl['acc'][1]} {fl['acc'][0]:.1f} deg/frame^2 at f{fl['acc'][2]} (max {ARM_ACC:.0f}), "
          f"stutters {len(fl['hitch'])} {fl['hitch'][:4]}, widest hand travel {fl['bulge'][0] * 100:.1f} cm off its line "
          f"({fl['bulge'][1]} f{fl['bulge'][2]}-{fl['bulge'][3]}, max {BULGE_MAX * 100:.0f}) -> {'OK' if fluid_ok else 'FAIL'}"
          + ("" if fluid_ok else ": slow the prop the hand carries there, or give reach() a longer lead/back"))
    ok = worst[0] <= WHIP_DEG and not pops and fluid_ok and reach_ok
    print(f"TWITCH {name}: fastest bone {worst[1]} {worst[0]:.1f} deg/frame at f{worst[2]} (fail over {WHIP_DEG:.0f}); "
          f"face pops {len(pops)} -> {'OK' if ok else 'FAIL'}")
    return ok
