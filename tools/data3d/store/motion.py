"""POP, HOLD and FAR: what failed the lightning short's rough cut, measured from the animation before a frame renders.

caaleb, 2026-11-20, of the lightning rough cut (every 4th proof frame): "good not great, clearly there are large scale
issues that need to be fixed". The judge panel failed four of five beats on the same three classes, and none of them
was measured by anything:

  POP   a big move happens between frames. The tower: Data on the stair landing at proof frame 31 and on the grass,
        metres closer, at 32. The ridge: on the grass at frame 2 and a body-height up in the air at 3. The beach: a
        0.80 m glide with his feet planted, "a camera push-in on a statue".
  HOLD  a beat ends on one held pose. The truck: an arm parked out with a fixed grin for 1.7 s. The beach: arms out,
        legs straight, frames 9-24.
  FAR   the event lands far from him, at the frame edge, a thin line on a phone; Data small at the moment that
        matters; a knockdown seen from the front, which reads as a hop.

POP  (Data's own move, the camera's taken out)
  SNAP   over one proof step (STEP frames, every 4th: what the judge's sheet shows), Data's core (head, chest, hips,
         feet) moves more than POP_MAX of the frame height on screen. It is the SMALLER of two readings: how far his
         points move on screen (what the viewer sees) and how far they move through the camera as it is NOW (his own
         move, so a whip pan, or a tracking camera that keeps a walking Data still on screen, is not his pop). A move
         that travels farther must take longer: POP_MAX per STEP frames is 0.75 of the frame height a second.
  GLIDE  both feet slide together, neither lifting, while his hips travel GLIDE_D or more: a slide, not a step.
  LEAP   both feet off their marks, lifted AIR_H or more, while his hips travel LEAP_D or more, must stay airborne at
         least AIR_MIN, so the leap has frames in the air on the sheet.
  SHOW   every window over SHOW_MIN is also a FAST MOVE: shots.py adds its in-between frames to a proof render, so
         the judge sees the move, not two ends of it (judge3d.strip marks them).
HOLD
  Data's POSE (his head, hands, elbows, knees, feet and chest, measured from his hips: a glide or a drift toward the
  lens is not a move) stays within HOLD_R of where it was for more than HOLD_MAX, anywhere in the shot, the final
  held payoff included (it may hold HOLD_MAX at most). A move smaller than HOLD_R (a 3 cm knuckle tap, a 0.1 m hop
  of his whole body) is no move: the truck's two raps measured 3 cm, and the judge saw "the same pose".
FAR (staging.far runs it)
  SIZE   at each of the beat's arc moments (script.json staging[].arc) he is at least FAR_H of the frame height,
         measured as his STANDING height at his head's depth, so lying flat or crouching does not shrink him.
  EVENT  every lightning strike (store/storm_kit.STRIKES) lands within FAR_GAP of him on screen, at least FAR_EDGE
         inside the frame's sides, and its glow is at least FAR_GLOW_PX wide at 1080 px. A strike more than
         SCENERY_M from him is scenery (the far storm over the valley), not an event, and is not measured.
  DROP   when he drops (a knockdown, a sit, a crouch: his head falls DROP of his standing height inside a second),
         the lens is at least DROP_SIDE degrees off his front: from the front a fall reads as a hop.

Calibration (2026-11-20, every frame of the animation dumped through the harness with no render; the failing takes
are the ones the judge failed, the passing one is the trail beat, shot4.py, which the panel passed at 72):

                      SNAP max   GLIDE max   HOLD max   SIZE at arc     strikes near him                    DROP side
  trail   (PASS, 72)   0.067      0.03 m      0.53 s     0.47-0.48       3: gap 0.04-0.06, glow 129-349 px   none
  tower   (56)         0.143      0.03 m      0.30 s     0.26 at .72     3 on the rod: gap 0.35-0.41         none
  ridge r3 (50)        0.157      0.07 m      0.63 s     0.28 at .49     bolt 1 at x 0.02 (the frame edge)   4-5 deg
  ridge repo           0.247      0.04 m      1.17 s     0.27 at .03     the oak bolt: glow 20 px            4-6 deg
  beach repo (52)      0.034      0           0.93 s     0.45-0.47       glow 20 px: a thin line             none
  beach r4 (44)        0.043      0.80 m      2.30 s     0.45-0.58       x 0.11, gap 0.20, glow 23 px        none
  truck (60)           0.045      0.09 m      1.93 s     0.26 at .36     bumper sparks: gap 0.31-0.35        none
(SNAP in frame heights per 4 frames; HOLD at HOLD_R = 7 cm, the longest stretch; SIZE is his standing height at his
head's depth.) The tower's leap (0.143 at frames 121-125, exactly where the judge saw the teleport), the ridge
rewrite's launch off the grass (0.157, frames 6-10) and the repo ridge's dive (0.247, with 4 frames in the air) are
POPs; the trail's walk is 0.067. The beach rewrite's 0.80 m glide is the only GLIDE over 0.25 m. The truck's arm
parked out, the beach's statue and the repo ridge lying still are dead HOLDs; the trail's longest still is 0.53 s.
Every failing take fails FAR on at least one count; the trail passes every one.
Not measured: what the judge called "reads as a glide" in the tower's sprint (his legs DO step: a style of step, not
a slide), and whether a bolt lands where the script says ("behind him", not "in front"): a direction in the words.
"""
import math

FPS_ = 30
STEP = 4               # frames between proof frames: what the judge's contact sheet shows (judge3d BAR: "every 4th")
POP_MAX = 0.10         # of the frame height, per STEP frames (0.75 frame heights a second): over it is a teleport
SHOW_MIN = 0.08        # of the frame height per STEP frames: a FAST MOVE, whose in-betweens go on the judge's sheet. Over
                       # the trail's tracked walk (0.067), so a proof does not render every frame of an ordinary walk
GLIDE_D = 0.25         # m his hips travel while both feet slide flat: a glide
FOOT_V = 0.005         # m per frame: a foot that moves
LIFT_V = 0.004         # m per frame: a foot that lifts or lands
LEAP_D = 0.30          # m his hips travel in the air: a leap
AIR_H = 0.04           # m both feet above where they took off and landed: in the air
AIR_MIN = 8            # frames (0.27 s): two proof frames of a leap are in the air
HOLD_R = 0.07          # m (8% of his 0.88 m height): a pose change smaller than this is no move
HOLD_MAX = 0.8         # s of one held pose, anywhere, the final payoff included

FAR_H = 0.32           # of the frame height, his standing height at each arc moment. The smallest any passed shot had:
                       # cardrewards shot 3 (passed at 72) measured 0.32 on its storyboard; the trail passed at 0.48;
                       # the failing tower measured 0.27 at its leap, the ridge rewrite 0.29 at its big bolt
FAR_GAP = 0.18         # of the frame height: the farthest a strike may land from the nearest part of him on screen
FAR_EDGE = 0.12        # of the frame width: a strike lands at least this far inside the frame's sides (staging.EDGE)
FAR_GLOW_PX = 40.0     # px at 1080 wide: the strike's glow (its radius) where it lands, or it is a thin line on a phone
SCENERY_M = 6.0        # m from him: a strike farther than this is the storm's scenery, not an event of the beat
DROP = 0.20            # of his standing height, lost inside a second: a knockdown, a sit, a crouch
DROP_SIDE = 30.0       # degrees: the lens at least this far off his front/back axis while he drops (three-quarter)
STAND = 0.69           # m: his head top (the head bone's tail) above his feet, standing (the rig; it never changes)


def _d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def snaps(screen, own, step=STEP):
    """screen[i]: Data's core points on screen at frame i+1 (x, y in frame HEIGHTS, so a move across the width counts
    the same as one up the height); own[i]: the core points of frame i+1-step seen through frame i+1's camera (None
    before step frames). [(f0, f1, amount)] for every window: amount = min(on-screen change, his own move)."""
    out = []
    for i in range(step, len(screen)):
        if own[i] is None: continue
        scr = max((_d2(p, q) for p, q in zip(screen[i - step], screen[i]) if p and q), default=0.0)
        mine = max((_d2(p, q) for p, q in zip(own[i], screen[i]) if p and q), default=0.0)
        out.append((i + 1 - step, i + 1, min(scr, mine)))
    return out


def pops(windows, limit=POP_MAX):
    """the windows over the limit, merged into moves: [(f0, f1, worst)]"""
    out = []
    for f0, f1, a in windows:
        if a <= limit: continue
        if out and f0 <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], f1), max(out[-1][2], a))
        else:
            out.append((f0, f1, a))
    return out


def _hd(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def glides(foot_l, foot_r, hips, d=GLIDE_D):
    """per-frame world points (x, y, z). [(f0, f1, metres)] of every run where both feet slide (each moves FOOT_V a
    frame, neither lifts LIFT_V) while his hips travel d or more"""
    out, a = [], None
    n = len(hips)
    for i in range(1, n + 1):
        sl = i < n and _hd(foot_l[i], foot_l[i - 1]) > FOOT_V and _hd(foot_r[i], foot_r[i - 1]) > FOOT_V \
            and abs(foot_l[i][2] - foot_l[i - 1][2]) < LIFT_V and abs(foot_r[i][2] - foot_r[i - 1][2]) < LIFT_V
        if sl and a is None: a = i - 1
        if not sl and a is not None:
            b = i - 1; m = _hd(hips[b], hips[a])
            if m >= d: out.append((a + 1, b + 1, m))
            a = None
    return out


def leaps(foot_l, foot_r, hips, d=LEAP_D, air_min=AIR_MIN):
    """[(f0, f1, metres, frames_in_air)] for every leap (both feet moving, his hips travelling d or more) whose feet
    were in the air (AIR_H over the line between where they took off and where they landed) fewer than air_min frames"""
    out, a = [], None
    n = len(hips)
    for i in range(1, n + 1):
        mv = i < n and math.dist(foot_l[i], foot_l[i - 1]) > FOOT_V and math.dist(foot_r[i], foot_r[i - 1]) > FOOT_V
        if mv and a is None: a = i - 1
        if not mv and a is not None:
            b = i - 1; m = math.dist(hips[b], hips[a])
            if m >= d:
                air = 0
                for k in range(a, b + 1):
                    u = (k - a) / max(1, b - a)
                    base = [foot_l[a][2] + (foot_l[b][2] - foot_l[a][2]) * u, foot_r[a][2] + (foot_r[b][2] - foot_r[a][2]) * u]
                    air += foot_l[k][2] - base[0] >= AIR_H and foot_r[k][2] - base[1] >= AIR_H
                if 0 < air < air_min:            # no air at all is a run down stairs or a glide (glides() has that)
                    out.append((a + 1, b + 1, m, air))
            a = None
    return out


def holds(pose, r=HOLD_R, fps=FPS_, skip=()):
    """pose[i]: his tracked points at frame i+1, measured from his hips (metres). [(f0, f1, seconds)] of every maximal
    stretch where every point stays within r of where it was at the stretch's start. skip: frames not judged (a cutaway)"""
    n = len(pose); ext = []
    for a in range(n):
        b = a
        while b + 1 < n and (b + 2) not in skip and max(math.dist(p, q) for p, q in zip(pose[a], pose[b + 1])) < r:
            b += 1
        ext.append(b)
    out, mx = [], -1
    for a in range(n):
        if (a + 1) in skip: continue
        if ext[a] > mx:
            if ext[a] > a: out.append((a + 1, ext[a] + 1, (ext[a] - a) / fps))
            mx = ext[a]
    return out


def dead_holds(stretches, hold_max=HOLD_MAX):
    return [s for s in stretches if s[2] > hold_max + 1e-9]


def drops(head_h, side_deg, fps=FPS_, stand=STAND):
    """head_h[i]: his head top's height above the lower of his feet and hips at frame i+1 (m); side_deg[i]: how far the
    lens is off his front/back axis (0 front or back, 90 a profile). [(f, drop, side)] for the frames of a drop
    (DROP of his standing height lost inside a second) seen within DROP_SIDE of his front"""
    out = []
    for i, h in enumerate(head_h):
        dr = (max(head_h[max(0, i - fps):i + 1]) - h) / stand
        if dr >= DROP and side_deg[i] < DROP_SIDE: out.append((i + 1, dr, side_deg[i]))
    return out


def strike_problems(p, gap, glow_px, edge=FAR_EDGE):
    """one strike at the frame it lands: p = (x, y, depth) in the frame (0..1), gap = frame heights from it to the
    nearest part of him on screen, glow_px = its glow's radius at 1080 px. The problems, or []"""
    out = []
    if p[2] <= 0 or not (0 <= p[1] <= 1) or not (edge <= p[0] <= 1 - edge):
        out.append(f"lands at the frame edge or outside it (x {p[0]:.2f}, y {p[1]:.2f}; keep it {edge:.2f} inside)")
    if gap > FAR_GAP:
        out.append(f"lands {gap:.2f} of the frame height from him (max {FAR_GAP})")
    if glow_px < FAR_GLOW_PX:
        out.append(f"a thin line on a phone (its glow {glow_px:.0f} px across its radius at 1080 wide, min {FAR_GLOW_PX:.0f})")
    return out


# ---------------------------------------------------------------- the measurements, from the animation (bpy)
CORE = (("head", 1), ("head", 0), ("chest", 0), ("root", 0), ("foot.L", 1), ("foot.R", 1))
POSE = (("head", 1), ("hand.L", 1), ("hand.R", 1), ("fore.L", 0), ("fore.R", 0), ("foot.L", 1), ("foot.R", 1),
        ("chest", 1), ("shin.L", 0), ("shin.R", 0))


def _pt(data, b, tail):
    pb = data.pb[b]; return data.arm.matrix_world @ (pb.tail if tail else pb.head)


def sample(data, cam, nf, step=STEP):
    """every frame: his core points on screen, the same points `step` frames earlier through this frame's camera, his
    feet and hips in the world, and his pose from his hips"""
    import bpy
    from bpy_extras.object_utils import world_to_camera_view as w2c
    sc = bpy.context.scene; asp = sc.render.resolution_x / sc.render.resolution_y
    world, feet_l, feet_r, hips, pose = [], [], [], [], []
    for f in range(1, nf + 1):
        sc.frame_set(f)
        world.append([_pt(data, b, t) for b, t in CORE])
        r = _pt(data, "root", 0); hips.append(tuple(r)); feet_l.append(tuple(_pt(data, "foot.L", 1))); feet_r.append(tuple(_pt(data, "foot.R", 1)))
        pose.append([tuple(_pt(data, b, t) - r) for b, t in POSE])
    screen, own = [], []
    for f in range(1, nf + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        def P(p):
            q = w2c(sc, cam, p); return (q.x * asp, q.y) if q.z > 0 else None
        screen.append([P(p) for p in world[f - 1]])
        own.append([P(p) for p in world[f - 1 - step]] if f > step else None)
    return dict(screen=screen, own=own, feet_l=feet_l, feet_r=feet_r, hips=hips, pose=pose)


def check(data, cam, nf, name="shot", cutaway=None, fps=FPS_):
    """POP and HOLD. Prints a POP and a HOLD line; returns (ok, fast windows [(f0, f1)] for the in-between frames)"""
    m = sample(data, cam, nf)
    skip = set()
    if cutaway:
        skip = {f for f in range(1, nf + 1) if cutaway[0] <= (f - 1) / fps < cutaway[1]}
    win = [w for w in snaps(m["screen"], m["own"]) if not (set(range(w[0], w[1] + 1)) & skip)]
    pp = pops(win); gl = glides(m["feet_l"], m["feet_r"], m["hips"]); lp = leaps(m["feet_l"], m["feet_r"], m["hips"])
    fast = [(a, b) for a, b, _ in pops(win, SHOW_MIN)] + [(a, b) for a, b, *_ in lp]
    worst = max(win, key=lambda w: w[2]) if win else (0, 0, 0.0)
    pop_ok = not pp and not gl and not lp
    print(f"POP {name}: fastest move of his own {worst[2]:.3f} of the frame height in {STEP} frames at f{worst[0]}-{worst[1]} "
          f"(max {POP_MAX}: a teleport on the judge's sheet)"
          + "".join(f"; SNAP f{a}-{b} {x:.2f}" for a, b, x in pp[:4])
          + "".join(f"; GLIDE f{a}-{b}: his feet slide flat while he travels {x:.2f} m (max {GLIDE_D})" for a, b, x in gl[:3])
          + "".join(f"; LEAP f{a}-{b} ({x:.2f} m) with {k} frames in the air (min {AIR_MIN})" for a, b, x, k in lp[:3])
          + f"; fast moves shown frame by frame: {fast[:6]} -> {'OK' if pop_ok else 'FAIL: slow it so it takes longer, step it, or show it in the air'}",
          flush=True)
    st = holds(m["pose"], skip=skip); dead = dead_holds(st)
    longest = max(st, key=lambda s: s[2]) if st else (0, 0, 0.0)
    hold_ok = not dead
    print(f"HOLD {name}: longest held pose {longest[2]:.2f}s at f{longest[0]}-{longest[1]} (his pose within {HOLD_R * 100:.0f} cm; "
          f"max {HOLD_MAX}s, the final payoff included)"
          + "".join(f"; DEAD HOLD f{a}-{b} {s:.2f}s" for a, b, s in dead[:3])
          + f" -> {'OK' if hold_ok else 'FAIL: give him a new action inside every 0.8 s; a tap or a drift is not one'}", flush=True)
    return pop_ok and hold_ok, sorted(set(fast))
