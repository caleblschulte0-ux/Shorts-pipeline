"""STEADY: Data reads as ONE real person (caaleb 2026-11-23, of the lightning short: "he's doing too much. He's changing
emotions too often. He's, like, twidgeting too fast. His legs are kind of glitching out of his coat. Like, his head
moves really fast ... it makes it hard to get attuned with the character when he's constantly, like, shifting around
and, like, changing his faces ... Not that I'm saying we need to make him less reactive or more deadpan").

The rig makes him that way (character.py: face_plan casts the faces he shows from the faces a shot asks for,
look_plan the head turns, head_follow moves the head at a person's speed, alive() drifts low and slow, coat_weights
hangs the coat on the legs). This is the check that it did, measured on the built shot before a frame renders, beside
twitch and the face lint. Under STAGING=strict any FAIL fails the shot.

  FACES   the faces he shows (data.face_log, as cast): each held FACE_HOLD from its arrival to the next one's start
          (the last, which the cut ends, FACE_HOLD_CUT; the one a shot opens on before its first reason, FACE_OPEN), at most FACE_MAX starting in any FACE_WINDOW, each arriving over FACE_BLEND. The numbers are
          character.py's own, read from it, never restated here.
  HEAD    his head's turn against his hips (head, neck, chest and spine together; a walk turning his whole body is
          not his head): fastest HEAD_MAX deg/s, and its speed changes by at most HEAD_ACC deg/s per frame (a whip
          starts and stops in a frame).
  FIDGET  the share of the shot his head JITTERS: its turn in the world, frame by frame, off its own course over about a
          second (JIT_WIN frames either side) by more than FIDGET_DEG deg/s; at most FIDGET_MAX. A deliberate turn, a
          hop, a whole-body stagger all have a course; the shake on top of it is the twidgeting a viewer sees. (Against
          his hips it cannot be told apart from a stride's own counter-turn, which a person has too.)
  COAT    a thigh or shin through the coat's wall (not out under its hem): deeper than COAT_POKE on more than GRACE
          frames fails. Measured as the coat's skin inside a leg's capsule; the hem's underside and the hip's own ball
          (the joint, inside his body) are not the wall.

Lightning, as posted (2026-11-23, every frame of the five shots, no render), against these:
  faces a shot 4-8, held 0.10-0.56 s at the shortest, 6.3-8.6 changes per 6 s; head against hips 141-310 deg/s at
  its fastest, its speed changing 32-84 deg/s in a frame; head jittering on 73-97% of frames (median 32-66 deg/s off
  its course); coat walls sunk 2.5-3.2 cm into a leg on 57-180 frames a shot.
The same five shots built by the steady rig: faces 2-3 a shot, 1.4-2.9 changes per 6 s; head 60-103 deg/s, 12-28 in a
frame; jittering on 16-50% (median 10-20); the coat 0-11 frames (shot 2's hot-foot high knee, 3.0 cm, and shot 5's sit,
the thigh roots 1.1 cm into the seat, still FAIL).
Lines start with STEADY so proof_loop picks them up."""
import math, os, re
from pathlib import Path

_CH = (Path(__file__).resolve().parents[1] / "character.py").read_text()


def _const(name):
    m = re.search(rf"^{name}\s*=\s*([0-9.]+)", _CH, re.M)
    return float(m.group(1))


def _pair(name):
    m = re.search(rf"^{name}\s*=\s*([0-9.]+)\s*,\s*([0-9.]+)", _CH, re.M)
    return float(m.group(1)), float(m.group(2))


FACE_HOLD = _const("FACE_HOLD"); FACE_HOLD_CUT = _const("FACE_HOLD_CUT"); FACE_OPEN = _const("FACE_OPEN"); FACE_BLEND = _const("FACE_BLEND")
FACE_WINDOW, FACE_MAX = _pair("FACE_WINDOW, FACE_MAX")
HEAD_MAX = float(os.environ.get("STEADY_HEAD", "160"))   # deg/s, head against hips (lightning: 127-314)
HEAD_ACC = float(os.environ.get("STEADY_ACC", "40"))     # deg/s gained or lost in one frame (1200 deg/s^2)
FIDGET_DEG = 20.0      # deg/s off its own course: a shake
JIT_WIN = 15           # frames either side: the course is the head's turn averaged over about a second
FIDGET_MAX = float(os.environ.get("STEADY_FIDGET", "0.55"))
COAT_POKE = 0.006      # m: a leg through the coat this deep shows on a phone
GRACE = 2              # frames
FPS_ = 30
SLACK = 1.5 / FPS_     # s: a frame and a half of rounding


def face_problems(log, T, fps=FPS_):
    """[(t, why)] for a cast face log [(name, blend start, t0, t1, blend)] over a shot of T seconds. Pure."""
    log = sorted(log, key=lambda x: x[2])
    out = []
    starts = [max(0.0, e[2]) for e in log]
    for i, (nm, ta, t0, t1, bl) in enumerate(log):
        end = max(0.0, log[i + 1][1]) if i + 1 < len(log) else T      # held from its arrival to the next one's start
        need = FACE_OPEN if i == 0 and len(log) > 1 else FACE_HOLD_CUT if i == len(log) - 1 else FACE_HOLD
        if end - starts[i] < need - SLACK:
            out.append((starts[i], f"'{nm}' held {end - starts[i]:.2f} s (at least {need:.1f})"))
        if i and bl < FACE_BLEND - 1e-6:
            out.append((t0, f"'{nm}' arrives in {bl:.2f} s (at least {FACE_BLEND:.2f}): a pop"))
    for i in range(len(starts)):
        k = sum(1 for s in starts if starts[i] <= s < starts[i] + FACE_WINDOW)
        if k > FACE_MAX:
            out.append((starts[i], f"{k} faces start inside {FACE_WINDOW:.0f} s from {starts[i]:.2f} s (at most {FACE_MAX:.0f})"))
            break
    return out


def _qang(a, b):
    d = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2 * math.acos(min(1.0, d)))


def head_numbers(quats, fps=FPS_):
    """(fastest deg/s, sharpest change of speed deg/s per frame, share of frames turning faster than FIDGET_DEG) for a
    per-frame series of the head's rotation against his hips (unit quaternions as 4-tuples). Pure."""
    v = [_qang(quats[i - 1], quats[i]) * fps for i in range(1, len(quats))]
    if not v: return 0.0, 0.0, 0.0
    acc = max((abs(v[i] - v[i - 1]) for i in range(1, len(v))), default=0.0)
    return max(v), acc, sum(1 for x in v if x > FIDGET_DEG) / len(v)


def _qvel(a, b, fps):
    """the rotation vector (deg/s) that turns a into b in one frame"""
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    w = w1 * w2 + x1 * x2 + y1 * y2 + z1 * z2
    v = (w1 * x2 - x1 * w2 - y1 * z2 + z1 * y2, w1 * y2 + x1 * z2 - y1 * w2 - z1 * x2, w1 * z2 - x1 * y2 + y1 * x2 - z1 * w2)
    if w < 0: v = tuple(-c for c in v)
    s = math.sqrt(sum(c * c for c in v))
    if s < 1e-12: return (0.0, 0.0, 0.0)
    ang = math.degrees(2 * math.atan2(s, abs(w))) * fps
    return tuple(c / s * ang for c in v)


def jitter(quats, fps=FPS_, win=JIT_WIN):
    """(share of frames, median deg/s) the head's turn is off its own course by more than FIDGET_DEG. quats: per-frame
    unit quaternions of the head in the world. Pure."""
    v = [_qvel(quats[i - 1], quats[i], fps) for i in range(1, len(quats))]
    if not v: return 0.0, 0.0
    off = []
    for i in range(len(v)):
        a, b = max(0, i - win), min(len(v), i + win + 1)
        m = [sum(v[k][c] for k in range(a, b)) / (b - a) for c in range(3)]
        off.append(math.dist(v[i], m))
    return sum(1 for x in off if x > FIDGET_DEG) / len(off), sorted(off)[len(off) // 2]


def leg_pokes(coat_pts, legs, hem):
    """(count, deepest) of the coat's skin points inside a leg. coat_pts: world points; legs: [(a, b, r, is_thigh)]
    capsules (a the hip or knee end); hem: indices of points on the hem's underside. Pure (any 3-vectors with -, dot)."""
    n = 0; worst = 0.0
    for a, b, r, thigh in legs:
        ab = b - a; L2 = max(1e-12, ab.dot(ab))
        for k, p in enumerate(coat_pts):
            if k in hem: continue
            u = (p - a).dot(ab) / L2
            if thigh and u <= 0: continue                    # the hip's own ball: the joint, inside his body
            u = max(0.0, min(1.0, u)); d = r - (p - (a + ab * u)).length
            if d > 0.004: n += 1; worst = max(worst, d)
    return n, worst


def hem_of(data, coat):
    """the coat's skin points on its hem's underside (facing down at rest): inside it is under the coat, not the wall"""
    import bpy
    data.arm.data.pose_position = 'REST'; bpy.context.view_layer.update()
    ev = coat.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    R = coat.matrix_world.to_3x3()
    hem = {v for p in me.polygons if (R @ p.normal).normalized().z < -0.5 for v in p.vertices}
    ev.to_mesh_clear(); data.arm.data.pose_position = 'POSE'; bpy.context.view_layer.update()
    return hem


def check(data, nf, name="shot", fps=FPS_):
    import bpy
    sc = bpy.context.scene
    T = (nf - 1) / fps
    fp = face_problems(list(data.face_log), T, fps)
    coat = next((o for o in data.arm.children if o.name.startswith("Coat / continuous")), None)
    legs_r = {"leg": 0.162 * data.arm.scale[0], "shin": 0.150 * data.arm.scale[0]}   # the rig's capsules (character._build)
    hem = hem_of(data, coat) if coat is not None else set()
    quats, world, pokes = [], [], []
    for f in range(1, nf + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        pb = data.arm.pose.bones
        quats.append(tuple((pb["root"].matrix.inverted() @ pb["head"].matrix).to_quaternion()))
        world.append(tuple((data.arm.matrix_world @ pb["head"].matrix).to_quaternion()))
        if coat is None or f % 2 == 0 and f != nf: continue      # every other frame: a poke lasts longer than a frame
        M = data.arm.matrix_world
        ev = coat.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
        pts = [coat.matrix_world @ v.co for v in me.vertices]; ev.to_mesh_clear()
        legs = [(M @ pb[f"{b}.{s}"].head, M @ pb[f"{b}.{s}"].tail, legs_r[b], b == "leg") for s in "LR" for b in ("leg", "shin")]
        k, d = leg_pokes(pts, legs, hem)
        if d > COAT_POKE: pokes.append((f, d))
    top, acc, _ = head_numbers(quats, fps)
    busy, med = jitter(world, fps)
    face_ok = not fp
    head_ok = top <= HEAD_MAX and acc <= HEAD_ACC
    fidget_ok = busy <= FIDGET_MAX
    coat_ok = len(pokes) <= GRACE
    starts = sorted(max(0.0, e[2]) for e in data.face_log)
    holds = [b - a for a, b in zip(starts, starts[1:] + [T])]
    print(f"STEADY {name}: faces {len(starts)} {[e[0] for e in sorted(data.face_log, key=lambda x: x[2])]}, shortest held "
          f"{min(holds) if holds else 0:.2f} s -> {'OK' if face_ok else 'FAIL: ' + '; '.join(w for _, w in fp[:3])}", flush=True)
    print(f"STEADY {name}: head against his hips fastest {top:.0f} deg/s (max {HEAD_MAX:.0f}), sharpest change "
          f"{acc:.0f} deg/s in a frame (max {HEAD_ACC:.0f}) -> {'OK' if head_ok else 'FAIL: a head whip; let the turn take its time'}", flush=True)
    print(f"STEADY {name}: head jittering on {busy * 100:.0f}% of frames (off its own course by over {FIDGET_DEG:.0f} deg/s, "
          f"median {med:.0f}; max {FIDGET_MAX * 100:.0f}%) -> {'OK' if fidget_ok else 'FAIL: a shaking head; the neck must soak up the body (character.gaze_steady)'}", flush=True)
    print(f"STEADY {name}: a leg through the coat on {len(pokes)} frames" +
          (f" (deepest {max(d for _, d in pokes) * 100:.1f} cm, frames {[f for f, _ in pokes][:6]})" if pokes else "") +
          f" -> {'OK' if coat_ok else 'FAIL: the coat must ride the legs (character.coat_weights)'}", flush=True)
    return face_ok and head_ok and fidget_ok and coat_ok
