"""Data's arms move like arms (caaleb 2026-11-14: "sometimes data's movements are not the best or most fluid").
character.fluid relaxes an arm's per-frame rotation only around frames that change speed too suddenly or stutter,
never moves the frames a hand is on its job (IK contacts), and leaves a smooth move alone. store/twitch.py fails a
shot whose arms still snap, lurch or stutter."""
import ast, math
from pathlib import Path

D3 = Path(__file__).resolve().parents[1] / "tools" / "data3d"
SRC = (D3 / "character.py").read_text()


def _ns():
    tree = ast.parse(SRC)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ("_qang", "hot_frames", "fluid"))
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("ACC_MAX", "HITCH_DIP") for t in n.targets))]
    ns = {"math": math}
    exec(compile(ast.Module(keep, []), "character.py", "exec"), ns)
    return ns


def _series(angles_deg):
    """a rotation about one axis, one angle per frame, as the four quaternion component lists fluid() takes"""
    q = [(math.cos(math.radians(a) / 2), math.sin(math.radians(a) / 2), 0.0, 0.0) for a in angles_deg]
    return [[c[i] for c in q] for i in range(4)]


def _speeds(comps):
    ns = _ns(); q = [tuple(comps[i][k] for i in range(4)) for k in range(len(comps[0]))]
    return [ns["_qang"](q[k - 1], q[k]) for k in range(1, len(q))]


def test_a_sudden_swing_is_eased():
    ns = _ns()
    ang = [0.0] * 20 + [i * 20.0 for i in range(1, 6)] + [100.0] * 20      # 0 -> 20 deg/frame in one frame, then dead stop
    before = _speeds(_series(ang))
    after = _speeds(ns["fluid"](_series(ang)))
    acc = lambda v: max(abs(v[i] - v[i - 1]) for i in range(1, len(v)))
    assert acc(before) > 15
    assert acc(after) < acc(before) / 2
    c = ns["fluid"](_series(ang))
    path = [2 * math.degrees(math.atan2(c[1][k], c[0][k])) for k in range(len(ang))]
    assert abs(path[-1] - 100.0) < 0.5                                     # it still gets all the way there
    assert min(path) > -6 and max(path) < 106                               # a touch of wind-up and settle, no wobble


def test_contact_frames_never_move():
    ns = _ns()
    ang = [0.0] * 15 + [i * 15.0 for i in range(1, 7)] + [90.0] * 15
    c0 = _series(ang); pins = set(range(15, 21))
    c1 = ns["fluid"](c0, pins)
    for k in pins:
        assert all(abs(c0[i][k] - c1[i][k]) < 1e-12 for i in range(4))


def test_a_smooth_move_is_left_alone():
    ns = _ns()
    ang = [90.0 * (0.5 - 0.5 * math.cos(math.pi * k / 40)) for k in range(41)]   # eased over 40 frames
    c0 = _series(ang)
    assert not ns["hot_frames"]([tuple(c0[i][k] for i in range(4)) for k in range(41)])[0]
    c1 = ns["fluid"](c0)
    assert all(abs(c0[i][k] - c1[i][k]) < 1e-12 for i in range(4) for k in range(41))


def test_a_stutter_is_found():
    ns = _ns()
    ang, a = [], 0.0
    for k in range(30):
        a += 0.4 if k == 15 else 5.0                                         # moving, all but stops one frame, moves on
        ang.append(a)
    c = _series(ang)
    hot, _ = ns["hot_frames"]([tuple(c[i][k] for i in range(4)) for k in range(30)])
    assert any(13 <= k <= 18 for k in hot)


def test_the_twitch_check_fails_unfluid_arms():
    src = (D3 / "store" / "twitch.py").read_text()
    assert "ARM_FAST" in src and "ARM_ACC" in src and "fluid_ok" in src
    assert "and fluid_ok" in src            # a jerky arm fails the shot, not just a log line


def test_smooth_runs_the_fluid_pass_on_the_arms_with_contacts_pinned():
    tree = ast.parse(SRC)
    sm = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "smooth")
    code = ast.unparse(sm)
    assert "fluid(" in code and "_ik_keys" in code


# THE HAND TRAVELS, NOT THE JOINTS (caaleb 2026-11-14: "his arms will bend goofy"). In the posted saffron short his arm
# swung out like a wing on the way to the money: reach() slerped joint angles to a job that was out of his reach.

class _V:
    """a 3-vector with just what twitch.bulge uses, so the test runs without Blender's mathutils"""
    def __init__(self, *c): self.c = c
    def __sub__(self, o): return _V(*(a - b for a, b in zip(self.c, o.c)))
    def __add__(self, o): return _V(*(a + b for a, b in zip(self.c, o.c)))
    def __mul__(self, k): return _V(*(a * k for a in self.c))
    def dot(self, o): return sum(a * b for a, b in zip(self.c, o.c))
    @property
    def length(self): return math.sqrt(self.dot(self))


def _bulge():
    tree = ast.parse((D3 / "store" / "twitch.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "bulge")
    ns = {}
    exec(compile(ast.Module([fn], []), "twitch.py", "exec"), ns)
    return ns["bulge"]


def test_a_wing_swing_is_measured_off_its_line():
    bulge = _bulge()
    line = [_V(0.3 * u, 0.0, 0.0) for u in (i / 10 for i in range(11))]
    wing = [_V(0.3 * u, 0.0, 0.2 * math.sin(math.pi * u)) for u in (i / 10 for i in range(11))]
    assert bulge(line) < 1e-9
    assert abs(bulge(wing) - 0.2) < 1e-6
    src = (D3 / "store" / "twitch.py").read_text()
    assert "BULGE_MAX" in src and 'fl["bulge"][0] <= BULGE_MAX' in src     # a wing fails the shot
    assert "- shoulder[side]" in src           # measured in his frame: his body's own move is not the hand's bulge


def test_a_job_out_of_reach_fails_the_shot():
    src = (D3 / "store" / "twitch.py").read_text()
    assert "SHORT_MAX" in src and "reach_ok" in src and "and reach_ok" in src


def test_the_hand_path_is_one_chain_of_solves_in_his_frame():
    tree = ast.parse(SRC)
    fn = lambda name: ast.unparse(next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name))
    hp = fn("_hand_path")
    assert "range(fa + 1, fb)" in hp and "range(fb - 1" not in hp      # time order: the elbow never meets itself flipped
    assert "_shoulder_w" in hp and "r0.lerp(r1" in hp                   # the line is off the shoulder, not the world
    assert "PATH_CLEAR" in hp                                           # never through his own shoulder
    rc = fn("reach")
    assert rc.index("ik_end=True") < rc.index("_arm_ik(side, Vector(fn(t))")   # the path is solved before the job
    assert "on_job" in rc                       # a hand leaving one job for the next leaves from that job's solve
