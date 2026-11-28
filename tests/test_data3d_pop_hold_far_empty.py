"""POP, HOLD, FAR and EMPTY: what failed the lightning rough cut, measured before a judge is paid to say it.

caaleb, 2026-11-20, of the lightning rough cut (every 4th proof frame): "good not great, clearly there are large scale
issues that need to be fixed". The judge panel failed four of five beats on the same classes:
  POP    the tower's leap: on the stair landing at proof frame 31, on the grass metres closer at 32; the beach rewrite's
         0.80 m glide on planted feet
  HOLD   the truck's arm parked out with a fixed grin for 1.7 s; the beach's statue, frames 9-24
  FAR    bolts landing at the frame edge or far from him, a thin line on a phone; a knockdown seen from the front
  EMPTY  "a flat lawn with cutout pines", "a lit cabin", "an empty plane"
store/motion.py (POP, HOLD, the FAR rules), staging.far and store/empty.py measure them; shots.py fails a held story's
shot on any of them before a frame is judged.

The fixtures in tests/fixtures/data3d_motion/ are the REAL animation of each lightning take the judge saw, dumped
frame by frame through the harness with no render (store/shots.py, DIAG): Data's core points on screen and through
the camera of the frame, his feet, hips and pose. The trail beat (shot4.py) is the one the panel passed (72); every
check must pass it and fail the moments the judge named."""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
FIX = Path(__file__).resolve().parent / "fixtures" / "data3d_motion"
sys.path.insert(0, str(STORE)); sys.path.insert(0, str(STORE.parent))
import motion as MO  # noqa: E402


def _load(name):
    d = json.loads((FIX / f"{name}.json").read_text())
    sc = lambda p: (p[0] / 1e4, p[1] / 1e4) if p else None
    w = lambda v: tuple(x / 1000 for x in v)
    return dict(screen=[[sc(p) for p in f] for f in d["screen"]], own=[[sc(p) for p in f] if f else None for f in d["own"]],
                feet_l=[w(v) for v in d["feet_l"]], feet_r=[w(v) for v in d["feet_r"]], hips=[w(v) for v in d["hips"]],
                pose=[[w(v) for v in f] for f in d["pose"]], head_h=[x / 1000 for x in d["head_h"]], side=d["side"], NF=d["NF"])


PASSING = "trail_pass72"
FAILING = ["tower_fail56", "ridge_rewrite_fail50", "ridge_repo", "beach_fail52", "beach_rewrite_fail44", "truck_fail60"]


def _pop(m):
    win = MO.snaps(m["screen"], m["own"])
    return MO.pops(win), MO.glides(m["feet_l"], m["feet_r"], m["hips"]), MO.leaps(m["feet_l"], m["feet_r"], m["hips"]), win


def _hold(m):
    return MO.dead_holds(MO.holds(m["pose"]))


# ---------------------------------------------------------------- the passing beat passes every motion check
def test_the_trail_beat_the_judge_passed_passes_pop_and_hold():
    m = _load(PASSING)
    pp, gl, lp, win = _pop(m)
    assert not pp and not gl and not lp
    assert max(w[2] for w in win) == pytest.approx(0.067, abs=0.003)          # its walk, tracked: the calibration
    assert not MO.pops(win, MO.SHOW_MIN), "an ordinary walk adds no in-between frames to the proof"
    assert not _hold(m)
    assert max(s[2] for s in MO.holds(m["pose"])) < 0.6                         # its longest still: 0.53 s
    assert not MO.drops(m["head_h"], m["side"])


# ---------------------------------------------------------------- POP
def test_the_towers_teleport_is_a_pop_exactly_where_the_judge_saw_it():
    """judge, tower round 2: "Data is three or four rungs up the last flight in 31 and on the grass a few metres closer
    to the lens in 32" -- proof frames 31 and 32 are frames 121 and 125 of the shot"""
    pp, *_ = _pop(_load("tower_fail56"))
    assert any(a <= 121 and b >= 125 and x > MO.POP_MAX for a, b, x in pp)
    assert max(x for *_, x in pp) == pytest.approx(0.143, abs=0.005)


def test_the_ridges_launch_and_dive_are_pops():
    pp, *_ = _pop(_load("ridge_rewrite_fail50"))
    assert any(a <= 6 and b >= 10 for a, b, _ in pp)                            # off the grass, a body-height up, frames 6-10
    pp, gl, lp, _ = _pop(_load("ridge_repo"))
    assert max(x for *_, x in pp) > 0.2                                         # the dive: 0.247 of the frame in 4 frames
    assert lp and lp[0][3] < MO.AIR_MIN                                         # and only 4 frames in the air


def test_the_beach_glide_on_planted_feet_is_a_pop():
    """judge, beach rewrite: "it reads as a camera push-in on a statue, not a ranger skidding across glass" """
    _, gl, _, _ = _pop(_load("beach_rewrite_fail44"))
    assert gl and gl[0][2] == pytest.approx(0.80, abs=0.03) and gl[0][2] > MO.GLIDE_D
    for name in [PASSING] + [n for n in FAILING if n != "beach_rewrite_fail44"]:
        assert not _pop(_load(name))[1], f"{name}: nothing else glides (the widest is 0.09 m)"


def test_a_leap_needs_frames_in_the_air():
    n = 40
    hips = [(0.0, -0.03 * i, 0.3) for i in range(n)]
    lift = lambda i: 0.2 if 12 <= i < 15 else 0.0                               # 3 frames up: a hop that reads as a pop
    feet = [(0.0, -0.03 * i, lift(i)) for i in range(n)]
    assert MO.leaps(feet, feet, hips) and MO.leaps(feet, feet, hips)[0][3] == 3
    lift = lambda i: 0.2 if 8 <= i < 24 else 0.0                                # 16 frames up: a leap with air
    feet = [(0.0, -0.03 * i, lift(i)) for i in range(n)]
    assert not MO.leaps(feet, feet, hips)


def test_a_fast_move_s_in_betweens_are_named():
    """the tower's leap is fast enough that its in-betweens go into the proof (judge3d.strip marks them)"""
    win = MO.snaps(*[_load("tower_fail56")[k] for k in ("screen", "own")])
    fast = MO.pops(win, MO.SHOW_MIN)
    assert any(a <= 121 and b >= 125 for a, b, _ in fast)
    assert MO.SHOW_MIN < MO.POP_MAX


# ---------------------------------------------------------------- HOLD
def test_the_trucks_parked_arm_is_a_dead_hold():
    """judge: "frames 29-40, about 12 frames (around 1.7 s) of almost the same pose": shot frames 113-157. The two
    knuckle raps in it moved his hand 3 cm, which no viewer saw: a move under HOLD_R is no move"""
    dead = _hold(_load("truck_fail60"))
    assert any(a <= 113 + 5 and b >= 135 for a, b, _ in dead)
    assert max(s for *_, s in dead) > 1.5


def test_the_beach_statue_and_the_ridge_lying_still_are_dead_holds():
    for name in ("beach_fail52", "beach_rewrite_fail44", "ridge_repo"):
        dead = _hold(_load(name))
        assert dead and max(s for *_, s in dead) > MO.HOLD_MAX, name
    assert max(s for *_, s in _hold(_load("beach_rewrite_fail44"))) > 2.0     # frames 9-24 of the sheet and on


def test_a_hold_is_measured_from_his_hips_so_a_glide_is_still_a_hold():
    pose = [[(0.1, 0.0, 0.5), (0.0, 0.1, 0.3)] for _ in range(60)]             # the same pose for two seconds
    assert MO.dead_holds(MO.holds(pose))
    wave = [[(0.1, 0.0, 0.5), (0.0, 0.1 + 0.15 * math.sin(i / 6), 0.3)] for i in range(60)]   # an arm that moves
    assert not MO.dead_holds(MO.holds(wave))
    tap = [[(0.1, 0.0, 0.5), (0.0, 0.1 + 0.015 * math.sin(i), 0.3)] for i in range(60)]       # a 3 cm tap: no move
    assert MO.dead_holds(MO.holds(tap))


def test_a_cutaway_is_not_his_hold():
    pose = [[(0.1, 0.0, 0.5)] for _ in range(60)]
    assert not MO.dead_holds(MO.holds(pose, skip=set(range(20, 61))))


# ---------------------------------------------------------------- FAR
def test_a_knockdown_seen_from_the_front_is_far():
    """judge, ridge rewrite: "the second bolt never knocks him onto his rump" -- it did, seen from the front"""
    for name in ("ridge_rewrite_fail50", "ridge_repo"):
        m = _load(name); dr = MO.drops(m["head_h"], m["side"])
        assert dr and max(d[2] for d in dr) < 10, name                           # 4-6 degrees off his front
    m = _load("ridge_rewrite_fail50")
    assert not MO.drops(m["head_h"], [60] * len(m["side"])), "the same fall from three-quarter passes"
    for name in [PASSING, "tower_fail56", "beach_fail52", "beach_rewrite_fail44", "truck_fail60"]:
        m = _load(name); assert not MO.drops(m["head_h"], m["side"]), name


# measured in the harness (staging.far, 2026-11-20): (x, y, depth) where it lands, its gap to him in frame heights,
# its glow's radius in px at 1080. (The tower's three rod strikes landed 0.35-0.41 of the frame from him, the truck's
# bumper sparks 0.31-0.35: FAR fails both on the gap alone.)
STRIKES = {
    "trail bolt 1 (PASS)": ((0.48, 0.73, 1.7), 0.04, 129.1),
    "trail bolt 2 (PASS)": ((0.52, 0.71, 1.6), 0.06, 136.1),
    "trail bolt 3 (PASS)": ((0.50, 0.73, 1.7), 0.06, 349.4),
    "ridge rewrite bolt 1: at the frame edge": ((0.02, 0.26, 1.8), 0.16, 93.7),
    "beach rewrite: far left edge, far from him": ((0.11, 0.47, 2.4), 0.20, 22.5),
    "beach: a thin line on a phone": ((0.43, 0.32, 2.6), 0.05, 20.3),
}


def test_a_strike_lands_near_him_inside_the_frame_and_reads():
    for name, (p, gap, glow) in STRIKES.items():
        probs = MO.strike_problems(p, gap, glow)
        assert bool(probs) == ("PASS" not in name), (name, probs)
    assert MO.strike_problems((0.11, 0.47, 2.4), 0.20, 22.5)[0].startswith("lands at the frame edge")


def test_his_size_at_each_arc_moment_is_calibrated_on_the_passed_shots():
    # the trail measured 0.47-0.49 at every arc moment; cardrewards shot 3 passed at 0.32 (its storyboard median);
    # the tower measured 0.26 at its leap and the ridge rewrite 0.28 at its big bolt
    assert 0.28 < MO.FAR_H <= 0.32 < 0.47


# ---------------------------------------------------------------- EMPTY
def _img(tmp_path, name, fn):
    np = pytest.importorskip("numpy"); Image = pytest.importorskip("PIL.Image")
    a = np.zeros((672, 378), np.uint8)
    for y in range(672):
        for x in range(0, 378, 6): a[y, x:x + 6] = fn(x, y)
    p = tmp_path / name; Image.fromarray(a).save(p); return p


def test_a_bare_set_is_empty_and_a_dressed_one_is_not(tmp_path):
    import empty
    bare = _img(tmp_path, "bare.png", lambda x, y: 60 + y // 12)                 # a sky-to-lawn gradient: one smooth plane
    import random
    rnd = random.Random(3)
    dressed = _img(tmp_path, "dressed.png", lambda x, y: rnd.randrange(40, 200) if (y // 6) % 2 else 90 + (x // 6) % 5 * 20)
    assert empty.emptiness(bare) > 0.9 > empty.EMPTY_MAX
    assert empty.emptiness(dressed) < 0.05
    assert not empty.check([(bare, None)] * 3) and empty.check([(dressed, None)] * 3)


def test_data_himself_is_masked_out_of_the_set(tmp_path):
    import empty
    half = _img(tmp_path, "half.png", lambda x, y: 120 if 150 <= x < 230 and 250 <= y < 520 else ((x * 37 + y * 91) % 160 + 40))
    assert empty.emptiness(half) > 0.0
    assert empty.emptiness(half, box=(150 / 378, 230 / 378, 1 - 520 / 672, 1 - 250 / 672)) < 0.02


def test_empty_is_calibrated_between_the_passed_and_the_bare_sets():
    import empty
    passed = {"trail": 0.11, "truck (not called bare)": 0.12, "checkout store, unmasked": 0.08}
    bare = {"tower": 0.31, "ridge rewrite": 0.33, "beach rewrite": 0.41, "beach": 0.49}
    assert max(passed.values()) < empty.EMPTY_MAX < min(bare.values())
    assert (empty.W, empty.B, empty.T) == (180, 6, 4.0), "the numbers above were measured at these settings"


# ---------------------------------------------------------------- wired, and it fails the proof before the judge
def test_every_check_runs_in_the_shot_harness_and_stops_a_held_shot():
    src = (STORE / "shots.py").read_text()
    for call in ("motion.check(data, sc.camera, NF", "staging.far(data, sc.camera, NF, _arc", "empty.check("):
        assert call in src, call
    for what in ("fails the motion check", "fails the FAR check", "fails the EMPTY check"):
        i = src.index(what); assert "raise SystemExit" in src[i - 120:i], what
    assert "_bind = fresh.held(STORY)" in src, "binding on every story made after fresh.py, like the other new checks"
    assert "INBETWEEN = sorted({f for a, b in FAST" in src and "inbetween.json" in src


def test_the_proof_loop_reads_the_lines_and_ci_fails_on_them():
    loop = (STORE / "proof_loop.py").read_text()
    import re
    rx = re.search(r'CHECKS = re\.compile\(r"(.*)"\)', loop).group(1)
    for k in ("POP", "HOLD", "FAR", "EMPTY"):
        assert re.match(rx, f"{k} shot 1: x -> FAIL"), k
    wf = (ROOT / ".github" / "workflows" / "data3d_render.yml").read_text()
    proof = wf[wf.index("- name: Proof pass"):wf.index("upload-artifact", wf.index("- name: Proof pass"))]
    assert "set -o pipefail" in proof and proof.index("set -o pipefail") < proof.index("| grep"), \
        "without pipefail the grep's status was the step's: a failed check went on to the judge"


def test_the_judges_sheet_marks_the_in_betweens(tmp_path, monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    monkeypatch.delenv("STORY", raising=False)
    import judge3d
    for n in (1, 2, 3, 5):
        Image.new("RGB", (90, 160), (40, 90, 40)).save(tmp_path / f"f{n:04d}.png")
    (tmp_path / "inbetween.json").write_text("[2, 3]")
    out = judge3d.strip(sorted(tmp_path.glob("f*.png")), tmp_path / "sheet.jpg", h=160, cols=4)
    S = Image.open(out).convert("RGB")
    band = lambda i: S.getpixel((i * 90 + 84, 4))            # right of the label
    assert band(0)[0] < 100 and band(3)[0] < 100                                # on the grid: no band
    assert band(1)[0] > 200 and band(2)[0] > 200 and band(1)[2] < 80            # the in-betweens: orange
    assert "IN-BETWEEN" in judge3d.BAR and "never time held" in judge3d.BAR
