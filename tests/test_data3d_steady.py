"""DATA IS ONE REAL PERSON (caaleb 2026-11-23, of the lightning short: "Data was much more reactive and involved in the
world. Big fan of that ... he's doing too much. He's changing emotions too often. He's, like, twidgeting too fast. His
legs are kind of glitching out of his coat. Like, his head moves really fast ... Not that I'm saying we need to make
him less reactive or more deadpan").

How he is MADE (tools/data3d/character.py): a shot ASKS for faces and looks, finish() CASTS what he shows (face_plan,
look_plan), the head and the bones carrying it FOLLOW the asked pose at a person's speed (head_follow), a held pose
drifts low and slow (alive, LIFE_AMP/LIFE_SLOW), and the coat rides the legs (coat_weights, with the legs solved at
their rest roll). store/steady.py fails a shot that still flickers, whips, fidgets or pokes a leg through the coat.

The failing cases are the lightning short's own numbers, measured on its five posted shots (every frame, no render):
the faces each shot asked for, which are the faces it showed."""
import ast, math, re, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
SRC = (D3 / "character.py").read_text()
NAMES = {"_face_sim", "face_plan", "look_plan", "head_follow", "_qmul", "_qrv", "coat_weights", "_sstep",
         "FACE_HOLD", "FACE_HOLD_CUT", "FACE_OPEN", "FACE_BLEND", "FACE_KIN", "KIN_SHARE", "FACE_WINDOW", "FACE_MAX", "LOOK_GAP", "LOOK_SMALL",
         "COAT_LEGS", "COAT_MID", "HEAD_LIMITS", "LIFE_AMP",
         "gaze_steady", "_qinv", "_gauss", "GAZE_SIG", "GAZE_HOLD", "GAZE_CAP", "GAZE_EASE"}


def _ns():
    keep = []
    for n in ast.parse(SRC).body:
        if isinstance(n, ast.FunctionDef) and n.name in NAMES: keep.append(n)
        elif isinstance(n, ast.Assign):
            ids = {getattr(t, "id", None) for t in n.targets} | {getattr(e, "id", None) for t in n.targets for e in getattr(t, "elts", [])}
            if ids & NAMES: keep.append(n)
    ns = {"math": math, "FPS": 30}
    exec(compile(ast.Module(keep, []), "character.py", "exec"), ns)
    return ns


sys.path.insert(0, str(D3 / "store"))
import steady as ST    # noqa: E402  (pure python: reads character.py's numbers, imports no Blender at module level)

# (name, blend start, t0, t1, blend) as each posted lightning shot asked for them, and the shot's length (s)
LIGHTNING = {
    1: (4.13, [("determined", -0.22, 0.0, 0.513, 0.22), ("surprised", 0.483, 0.563, 1.683, 0.08), ("alarmed", 1.683, 1.763, 3.17, 0.08),
               ("surprised", 3.14, 3.2, 3.28, 0.06), ("alarmed", 3.2, 3.3, 3.713, 0.1), ("worried", 3.633, 3.753, 5.167, 0.12)]),
    2: (5.17, [("worried", -0.22, 0.0, 0.39, 0.22), ("surprised", 0.37, 0.43, 1.1, 0.06), ("alarmed", 1.05, 1.2, 1.98, 0.15),
               ("surprised", 1.97, 2.03, 2.3, 0.06), ("alarmed", 2.28, 2.38, 3.18, 0.1), ("surprised", 3.17, 3.23, 4.05, 0.06),
               ("angry", 4.04, 4.14, 4.68, 0.1), ("deadpan", 4.64, 4.8, 6.2, 0.16)]),
    3: (4.70, [("determined", -0.22, 0.0, 0.247, 0.22), ("surprised", 0.227, 0.307, 0.817, 0.08), ("alarmed", 0.747, 0.867, 1.283, 0.12),
               ("angry", 1.273, 1.393, 2.227, 0.12), ("surprised", 2.227, 2.307, 3.517, 0.08), ("wry", 3.457, 3.637, 5.733, 0.18)]),
    4: (4.17, [("worried", -0.22, 0.0, 0.247, 0.22), ("surprised", 0.227, 0.307, 0.667, 0.08), ("alarmed", 0.607, 0.727, 1.24, 0.12),
               ("determined", 1.16, 1.28, 2.36, 0.12), ("surprised", 2.35, 2.43, 2.92, 0.08), ("worried", 2.84, 2.96, 3.194, 0.12),
               ("happy", 3.521, 3.681, 5.2, 0.16)]),
    5: (5.97, [("worried", -0.22, 0.0, 0.36, 0.22), ("alarmed", 0.36, 0.42, 3.433, 0.06), ("surprised", 3.383, 3.483, 4.333, 0.1),
               ("happy", 4.233, 4.383, 7.0, 0.15)]),
}


@pytest.mark.parametrize("shot", sorted(LIGHTNING))
def test_the_posted_faces_fail_and_the_cast_faces_pass(shot):
    T, asked = LIGHTNING[shot]
    assert ST.face_problems(asked, T), f"lightning shot {shot} as posted flickers between faces: the check must see it"
    plan = _ns()["face_plan"](asked, T)
    assert not ST.face_problems(plan, T), ST.face_problems(plan, T)
    assert 2 <= len(plan) <= 3, "he still REACTS (more than one face a beat), but as one person (two or three)"
    asked_at = {round(a[1], 3) for a in asked}
    for nm, ta, t0, t1, bl in plan[1:]:
        assert round(ta, 3) in asked_at, "a face changes only on a moment the shot asked for a change: its reason"
        assert nm in {a[0] for a in asked}


def test_a_shock_that_flickers_is_one_shock_and_the_payoff_face_survives():
    T, asked = LIGHTNING[1]
    names = [p[0] for p in _ns()["face_plan"](asked, T)]
    assert names[0] == "determined", "he walks in with the face the shot opens on, before anything has happened"
    assert sum(n in ("surprised", "alarmed") for n in names) == 1, "surprised / alarmed / surprised / alarmed is ONE shock"
    T, asked = LIGHTNING[5]
    assert [p[0] for p in _ns()["face_plan"](asked, T)][-1] == "happy", "the beat's payoff face (thumbs up) is kept"


def test_looks_asked_on_top_of_each_other_become_held_looks():
    ns = _ns()
    # lightning shot 1's looks: up, at us, down at his feet, at us, down again, at us, ... 0.35-0.45 s apart
    dirs = [(0.0, (0, 10)), (1.09, (5, 20)), (1.53, (0, 0)), (2.11, (10, -30)), (2.48, (0, 0)), (2.88, (10, -30)),
            (3.28, (-5, 0)), (3.40, (-5, 12)), (3.63, (0, 0))]
    keep = ns["look_plan"](dirs, 4.13)
    assert keep[0] == 0
    ts = [dirs[i][0] for i in keep]
    assert all(b - a >= ns["LOOK_GAP"] - 1e-9 for a, b in zip(ts, ts[1:]))
    assert 2 <= len(keep) < len(dirs), "he still looks round (more than one look), not at every cue"
    assert any(dirs[i][1][1] <= -25 for i in keep), "the big look (down at his burning feet) is one he turns for"


def _step(deg, n=60, at=10):
    q = [(math.cos(math.radians(0 if k < at else deg) / 2), 0.0, 0.0, math.sin(math.radians(0 if k < at else deg) / 2)) for k in range(n)]
    return [[c[i] for c in q] for i in range(4)]


def test_the_head_turns_at_a_persons_speed_and_settles():
    ns = _ns()
    vmax, amax = ns["HEAD_LIMITS"]["head"]
    c = ns["head_follow"](_step(40), vmax, amax)
    q = [tuple(c[i][k] for i in range(4)) for k in range(len(c[0]))]
    v = [ST._qang(q[k - 1], q[k]) * 30 for k in range(1, len(q))]
    assert max(v) <= vmax + 1e-6
    assert max(abs(v[k] - v[k - 1]) for k in range(1, len(v))) <= 1.25 * amax / 30, "it eases in and out (to a frame's rounding)"
    ang = [2 * math.degrees(math.atan2(x[3], x[0])) for x in q]
    assert abs(ang[-1] - 40) < 0.05 and max(ang) <= 40 + 1e-6, "it lands on its mark and never overshoots"
    raw = [tuple(_step(40)[i][k] for i in range(4)) for k in range(60)]
    assert ST.head_numbers(raw)[0] > ST.HEAD_MAX, "a 40 deg look keyed a frame away (the posted shots) fails HEAD"
    assert sum(v for v, _ in ns["HEAD_LIMITS"].values()) <= ST.HEAD_MAX, \
        "the bones that carry the head, all turning one way at once, are still under the check's limit"


def _bobbing(n=120, turn=40.0, bob=6.0, period=18):
    """a head turning `turn` deg over the shot while the body under it jolts +-`bob` deg every `period` frames (a hop, a
    stagger, a hop every 0.6 s: the posted lightning head shook 32-66 deg/s off its own course at the median)"""
    out = []
    for k in range(n):
        yaw = math.radians(turn) * (0.5 - 0.5 * math.cos(math.pi * k / (n - 1)))
        pit = math.radians(bob) * math.sin(2 * math.pi * k / period)
        qy = (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)); qx = (math.cos(pit / 2), math.sin(pit / 2), 0.0, 0.0)
        out.append(_ns()["_qmul"](qx, qy))
    return out


def test_the_neck_soaks_up_the_bodys_jolt_and_the_turn_still_happens():
    ns = _ns(); raw = _bobbing()
    D = ns["gaze_steady"](raw)
    held = [ns["_qmul"](d, q) for d, q in zip(D, raw)]
    before, after = ST.jitter(raw), ST.jitter(held)
    assert before[0] > ST.FIDGET_MAX, "a head bolted to a jolting body (the posted shots) fails FIDGET"
    assert after[0] <= ST.FIDGET_MAX and after[1] < before[1] / 2, (before, after)
    yaw = lambda q: math.degrees(math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))
    assert abs(yaw(held[-1]) - 40) < 3 and abs(yaw(held[60]) - yaw(raw[60])) < 3, "the deliberate turn passes through"
    assert max(2 * math.degrees(math.acos(min(1.0, abs(d[0])))) for d in D) <= ns["GAZE_CAP"] + 1e-6, "a neck, not a gimbal"
    cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == "Data")
    fin = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "finish"))
    assert fin.index("self.smooth(n)") < fin.index("self._steady_gaze(n)"), "steadied after the twitch filter, on what renders"


def test_a_held_pose_drifts_low_and_slow():
    cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == "Data")
    alive = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "alive"))
    assert "LIFE_AMP" in alive and "LIFE_SLOW" in alive
    assert _ns()["LIFE_AMP"] <= 0.5


def test_the_coat_rides_the_legs():
    w = _ns()["coat_weights"]
    for p in [(0.0, 0.0, 2.4), (0.3, -0.3, 1.9), (-0.4, 0.3, 1.0), (0.45, -0.3, 0.9), (0.0, -0.32, 0.9)]:
        assert abs(sum(w(p).values()) - 1.0) < 1e-9
    assert not any(k.startswith("leg") for k in w((0.0, -0.3, 1.9))), "the chest never follows a leg"
    hem_R = w((0.45, -0.3, 0.9)); hem_L = w((-0.45, -0.3, 0.9))
    assert hem_R.get("leg.R", 0) > 0.9 and hem_L.get("leg.L", 0) > 0.9, "the hem in front of a leg goes with it"
    mid = w((0.0, -0.32, 0.9))
    assert abs(mid["leg.L"] - mid["leg.R"]) < 1e-9, "the middle is shared"
    seat = w((0.3, 0.3, 1.3)); front = w((0.3, -0.3, 1.3))
    assert seat.get("leg.R", 0) < front["leg.R"], "the front follows higher than the back (a sit lifts the front over the lap)"


def test_the_legs_keep_their_roll_and_the_sewn_parts_ride_the_coat():
    cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == "Data")
    leg = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_leg_ik"))
    assert "roll_ref=" in leg, "the leg was solved turned over (rotation y ~180): the coat on it spun round the thigh"
    assert "COAT_SEWN" in SRC and "'Coat center seam'" in SRC


def test_leg_pokes_measures_the_wall_not_the_hem_or_the_hip():
    class V(tuple):
        def __new__(c, *a): return tuple.__new__(c, a)
        def __sub__(s, o): return V(*(a - b for a, b in zip(s, o)))
        def __add__(s, o): return V(*(a + b for a, b in zip(s, o)))
        def __mul__(s, k): return V(*(a * k for a in s))
        def dot(s, o): return sum(a * b for a, b in zip(s, o))
        @property
        def length(s): return math.sqrt(s.dot(s))
    thigh = (V(0, 0, 0.25), V(0, -0.1, 0.25), 0.032, True)          # lifted straight forward
    wall = [V(0, -0.05, 0.25), V(0, -0.06, 0.26)]                    # the coat's front, on the thigh
    assert ST.leg_pokes(wall, [thigh], set())[0] == 2
    assert ST.leg_pokes(wall, [thigh], {0, 1})[0] == 0, "the hem's underside is not the wall"
    assert ST.leg_pokes([V(0, 0.02, 0.25)], [thigh], set())[0] == 0, "behind the hip joint is the joint itself"


def test_the_check_runs_on_every_shot_and_proof_loop_reads_it():
    shots = (D3 / "store" / "shots.py").read_text()
    assert shots.index("import steady") > shots.index("import facelint")
    assert "steady.check(data, NF" in shots and 'raise SystemExit(f"shot {SHOT} fails the steady check' in shots
    assert "STEADY" in re.search(r"^CHECKS = re.compile\((.*)\)$", (D3 / "store" / "proof_loop.py").read_text(), re.M).group(1)
    cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == "Data")
    fin = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "finish"))
    assert fin.index("self._cast_looks(n)") < fin.index("self._cast_faces(n)") < fin.index("self._takes()"), \
        "the looks and faces are cast before the body takes them"
    sm = ast.unparse(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "smooth"))
    assert "head_follow(" in sm and "HEAD_LIMITS" in sm
    assert "CH.Data.SHOT_LEN = DUR" in shots, "the last face is held to the cut, not past it"


def test_a_walk_in_the_built_rig_keeps_the_legs_inside_the_coat():
    bpy = pytest.importorskip("bpy")
    sys.path.insert(0, str(D3))
    import character as CH
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    d = CH.load(bpy.context.scene)
    d.place(0.0, 0.0, 0.0)
    d.walk_to((0.0, -0.8), 0.1, 1.6)
    for s, ang in (("L", -60), ("R", 30)):      # and a big step: thigh up 60 deg in front, the other back
        d._k(f"leg.{s}", 1.9, rot=(ang, 0, 0)); d._k(f"shin.{s}", 1.9, rot=(-ang if ang < 0 else 0, 0, 0))
    n = d.finish()
    coat = next(o for o in d.arm.children if o.name.startswith("Coat / continuous"))
    hem = ST.hem_of(d, coat); bad = 0
    for f in range(1, n + 1, 3):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update(); M = d.arm.matrix_world
        ev = coat.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
        pts = [coat.matrix_world @ v.co for v in me.vertices]; ev.to_mesh_clear()
        legs = [(M @ d.pb[f"{b}.{s}"].head, M @ d.pb[f"{b}.{s}"].tail, (0.162 if b == "leg" else 0.150) * CH.SCALE, b == "leg")
                for s in "LR" for b in ("leg", "shin")]
        bad += ST.leg_pokes(pts, legs, hem)[1] > ST.COAT_POKE
    assert bad == 0
