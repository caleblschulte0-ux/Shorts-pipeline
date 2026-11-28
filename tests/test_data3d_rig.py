"""THE RIG AND THE MEASURED CHECKS (2026-11-14), held two ways: offline from the source, and on the real rig when a
Blender python (bpy) is available (DATA3D_BPY, or the session's venv), via tests/data3d_rig_probe.py.

  - EYES FOLLOW THE HEAD: look_at() turns the pupils onto the target by default (eyes=False opts out).
  - BIGGER LOOK-DOWN: past 22 deg a look tilts 1:1 up to 38 deg down, the neck taking what the head does not, layered in
    finish() on top of whatever else keys the neck; anatomy holds head+neck under HEAD_BEND_MAX.
  - MOTION YOU CAN SEE: a consequence may declare its moving part; its on-screen travel is MEASURED in pixels at the
    output resolution and must reach staging.MOVE_MIN of the frame height.
  - HANDS SOLVED LAST: every IK key is remembered and re-solved in finish() if a later body act moved it off its target.
  - THE PROP KIT: alarm_clock, wilt, zero_mark (and the wall clock) in store/prop_kit.py, EQUIVALENT to the inline code
    they came from (the originals kept verbatim in the probe as oracles)."""
import ast
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
CH_SRC = (D3 / "character.py").read_text()
CH = ast.parse(CH_SRC)
CLS = next(n for n in CH.body if isinstance(n, ast.ClassDef) and n.name == "Data")


def _method(name):
    return next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _tilt_fn():
    consts = {}
    for n in CLS.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Tuple) and "SOFT_PITCH" in ast.unparse(n.targets[0]):
            for t, v in zip(n.targets[0].elts, n.value.elts): consts[t.id] = v.value
    cls = type("C", (), consts)
    fn = _method("_tilt"); fn = ast.FunctionDef(**{**fn.__dict__, "decorator_list": []})
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module([fn], [])), "character.py", "exec"), ns)
    return lambda p: ns["_tilt"](cls, p)


def test_a_big_look_down_reads_and_a_small_one_is_unchanged():
    tilt = _tilt_fn()
    assert abs(tilt(-10) - (-6.0)) < 1e-9, "a small look is still 0.6 of the angle in the head"
    assert abs(tilt(-22) - (-13.2)) < 1e-9
    assert tilt(-60) == -38.0 and 35 <= -tilt(-60) <= 40, "a big look down tilts ~35-40 deg"
    assert tilt(60) == 25.0
    assert all(tilt(-a) >= tilt(-a - 1) for a in range(0, 80)), "monotonic"


def test_look_at_bends_the_neck_on_a_layer_and_moves_the_eyes():
    la = ast.unparse(_method("look_at"))
    assert "eyes=True" in la and "self._eye_looks.append(" in la and "self._neck_looks.append(" in la
    assert "max_pitch=60" in la, "the old 22 deg clamp is gone"
    fin = ast.unparse(_method("finish"))
    assert fin.index("self._layer_neck(n)") < fin.index("self._aim_eyes()") < fin.index("self.smooth(n)"), \
        "each pupil is aimed on the final body: after the neck layer, before the smoothing"
    anat = (D3 / "store" / "anatomy.py").read_text()
    assert float(re.search(r"^HEAD_BEND_MAX = ([0-9.]+)", anat, re.M).group(1)) <= 60
    assert 'hit("head bent off the neck"' in anat


def test_motion_is_measured_in_pixels_against_a_floor():
    src = (D3 / "store" / "staging.py").read_text()
    assert float(re.search(r"^MOVE_MIN = ([0-9.]+)", src, re.M).group(1)) >= 0.05, "a 2% flick failed the judge"
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "motion_px")
    ns = {}
    exec(compile(ast.Module([fn], []), "staging.py", "exec"), ns)
    mp = ns["motion_px"]
    proj = lambda p: (p[0], p[1], 1.0)                       # a flat stand-in camera: world x, y are the frame's 0..1
    assert mp({"a": [(0.5, 0.5, 0)]}, {"a": [(0.5, 0.56, 0)]}, proj, (1080, 1920)) == pytest.approx(0.06 * 1920)
    assert mp({"a": [(0.5, 0.5, 0)]}, {"a": [(0.5, 0.5, 0)]}, proj, (1080, 1920)) == 0
    cons = ast.unparse(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "consequence"))
    assert "motion_px(" in cons and "MOVE_MIN * res[1]" in cons and "'moves'" in cons


def test_hands_are_solved_after_the_body():
    assert "self._ik_keys[" in ast.unparse(_method("_arm_ik"))
    assert "self._ik_keys.pop(" in ast.unparse(_method("_k")), "an FK key on a frame replaces its IK solve"
    fin = ast.unparse(_method("finish"))
    assert fin.index("self._resolve_hands()") < fin.index("self.smooth(n)")
    banana = (D3 / "stories" / "banana" / "shots.py").read_text()
    assert "return data.reach(side, fn, t0, t1" in banana, "the story's reach delegates to the shared one"
    assert "HANDS shot" in (D3 / "store" / "shots.py").read_text()


def test_the_prop_kit_is_shared_and_saffron_uses_it():
    kit = (D3 / "store" / "prop_kit.py").read_text()
    for fn in ("def alarm_clock(", "def wilt(", "def zero_mark(", "def wall_clock(", "def spin_clock(", "def ring("):
        assert fn in kit, fn
    sk = (D3 / "store" / "saffron_kit.py").read_text()
    assert "from prop_kit import wall_clock, spin_clock" in sk and "def wall_clock(" not in sk, "one wall clock, not two"
    assert "PK.zero_mark(" in sk
    assert "prop_kit" in (D3 / "store" / "proof_loop.py").read_text(), "the reviser is told the kit exists"


# ---------------------------------------------------------------- on the real rig
def _bpy_python():
    c = os.environ.get("DATA3D_BPY") or os.environ.get("VBPY")      # the venv README.md says to make (bpy==5.0.0)
    if c and Path(c).exists():
        return c
    try:
        import bpy  # noqa: F401
        return sys.executable
    except Exception:
        return None


@pytest.fixture(scope="module")
def probe():
    py = _bpy_python()
    if not py:
        pytest.skip("no Blender python (bpy): set DATA3D_BPY to run the rig checks")
    p = subprocess.run([py, "-I", str(Path(__file__).with_name("data3d_rig_probe.py"))], capture_output=True, text=True, timeout=1500)
    line = next((l for l in p.stdout.splitlines() if l.startswith("PROBE ")), None)
    assert line, (p.stdout + p.stderr)[-3000:]
    return json.loads(line[6:])


def test_rig_the_face_lint_catches_the_defect_the_fix_removed(probe):
    assert probe["face_lint_with_fix"] is True
    assert probe["face_lint_without_fix"] is False


def test_rig_a_face_declared_later_owns_an_earlier_faces_blend_in(probe):
    """banana shot 1 as posted: the alarm smiled from 2.2 s to 2.8 s, back toward the rest key a flash had captured"""
    assert probe["hook_with_fix"] is True
    assert probe["hook_without_fix"] is False


def test_rig_wry_is_lopsided_and_the_face_reads_back(probe):
    assert probe["brow_sides"] == ["L", "R"]
    assert probe["wry_brow_dz_mm"] > 8, "one brow visibly above the other"
    assert probe["wry_state"]["cock"] == pytest.approx(1.0, abs=0.02) and probe["wry_state"]["side"] == pytest.approx(0.85, abs=0.02)
    for keys in (probe["lip_keys"], probe["inside_keys"]):
        assert {"side_R", "side_L"} <= set(keys)
    assert all(v < 1e-3 for v in probe["roundtrip_err"].values()), probe["roundtrip_err"]
    for k in ("worried", "alarmed", "surprised", "sad", "wry", "determined"):
        assert probe["smile_read"][k] <= 0.5, k


def test_rig_a_look_down_bends_the_neck_and_the_eyes_land_on_it(probe):
    assert 30 <= probe["look_down_bend_deg"] <= 45, probe["look_down_bend_deg"]
    assert probe["look_down_neck_deg"] >= 10, "the neck bends, over idle's breath keyed after the look"
    assert probe["gaze_off_target_deg"] < probe["head_off_target_deg"] - 5, "the eyes take what the head does not"
    assert probe["gaze_off_target_deg"] < 15
    assert probe["look_down_anatomy"] is True and probe["look_down_twitch"] is True


def test_rig_hands_are_back_on_the_prop_after_the_body_acts(probe):
    assert probe["hands_drift_unresolved_cm"] > 1.5, "the case bites: the body act does carry the hand off"
    assert probe["hands_drift_resolved_cm"] < 1.0 and probe["hands_resolved_frames"] > 0


def test_rig_a_flick_too_small_to_see_fails_and_a_big_swing_passes(probe):
    assert probe["motion_small_ok"] is False and probe["motion_big_ok"] is True


def test_rig_the_prop_kit_is_equivalent_to_the_code_it_came_from(probe):
    assert probe["kit_rows"] > 100
    assert probe["kit_equivalent"] is True, probe.get("kit_first_diff")
