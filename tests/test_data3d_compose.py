"""FRAME-FIRST PLACEMENT (caaleb, 2026-11-23: "our code is shit if it's cutting this off and putting them in the wrong
spot"): store/compose.py solves where a thing goes in the world from where it must sit on the screen. Its core is
plain math, so these run without Blender."""
import math
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parents[1] / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
import compose as C   # noqa: E402


def cube(c, s):
    return [(c[0] + dx * s, c[1] + dy * s, c[2] + dz * s) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]


def test_the_pinhole_is_scene_kits_lens():
    """a 36 mm vertical sensor: a point on the lens axis is the frame's centre, one at the half-angle its top edge"""
    cam = C.Pinhole((0, -2, 0.5), (0, 0, 0.5), 30)
    x, y, z = cam.project((0, 0, 0.5))
    assert abs(x - 0.5) < 1e-9 and abs(y - 0.5) < 1e-9 and abs(z - 2) < 1e-9
    top = cam.project((0, 0, 0.5 + 2 * 18 / 30))[1]
    assert abs(top - 1.0) < 1e-9
    right = cam.project((2 * 18 / 30 * 1080 / 1920, 0, 0.5))[0]
    assert abs(right - 1.0) < 1e-9


def test_a_sign_cut_by_the_edge_is_slid_into_its_box():
    cam = C.Pinhole((0, -2, 0.6), (0, 0, 0.6), 28)
    sign = cube((0.9, 0, 1.0), 0.15)                     # off the right edge
    b, _ = C.bbox(cam.project, sign)
    assert b[2] > 1.0
    box = (0.1, 0.72, 0.9, 0.95)
    r = C.fit(cam.project, sign, box, C.screen_axes(cam, False))
    assert r["ok"], r
    moved = [C._add(p, r["offset"]) for p in sign]
    assert C.inside(C.bbox(cam.project, moved)[0], box)


def test_a_prop_on_the_ground_keeps_its_foot_on_the_floor():
    cam = C.Pinhole((0.2, -1.6, 0.7), (0.2, 0.3, 0.6), 30)
    jar = [(x, y, z) for x in (-0.05, 0.05) for y in (-0.05, 0.05) for z in (0.0, 0.2)]
    box = (0.15, 0.1, 0.45, 0.4)
    r = C.fit(cam.project, jar, box, C.screen_axes(cam, True), on_ground=True, pivot=(0, 0, 0))
    assert r["ok"], r
    assert abs(r["offset"][2]) < 1e-9                    # slid on the floor, never lifted
    assert abs(r["box"][1] - box[1]) < 0.005             # its foot on the box's foot


def test_too_big_for_its_box_is_reported_or_scaled():
    cam = C.Pinhole((0, -1.5, 0.5), (0, 0, 0.5), 30)
    big = cube((0, 0, 0.5), 0.6)
    box = (0.3, 0.3, 0.7, 0.6)
    r = C.fit(cam.project, big, box, C.screen_axes(cam, False))
    assert not r["ok"] and "box" in r["why"]
    r = C.fit(cam.project, big, box, C.screen_axes(cam, False), scale_ok=True)
    assert r["ok"] and r["scale"] < 1


def test_data_is_framed_by_moving_the_camera_not_him():
    """his hands are on the set already: the lens trucks and dollies so his face lands where the shot wants it"""
    face, crown, foot = (0.5, 0.1, 0.55), (0.5, 0.1, 0.75), (0.5, 0.1, 0.0)
    loc, look, rep = C.solve_camera(face, crown, foot, (0.0, -1.5, 0.6), (0.0, 0.3, 0.6), 30, face_at=(0.35, 0.6), height=0.36)
    assert rep["ok"], rep
    cam = C.Pinhole(loc, look, 30)
    hx, hy, _ = cam.project(face)
    assert abs(hx - 0.35) < 0.01 and abs(hy - 0.6) < 0.01
    assert abs(cam.project(crown)[1] - cam.project(foot)[1] - 0.36) < 0.01


def test_every_honey_shot_is_placed_frame_first():
    """the five honey shots frame Data with compose.frame_data and declare their signs and key props' boxes"""
    src = (STORE.parent / "stories" / "honey" / "shots.py").read_text()
    for n in range(1, 6):
        body = src[src.index(f"def shot{n}():"):]
        nxt = body.find("\ndef ", 10)
        body = body[:nxt if nxt > 0 else None]
        assert "frame_data(" in body, n
        assert '"boxes"' in body or "boxes=" in body, n


def test_the_harness_runs_the_boxes_strict():
    src = (STORE / "shots.py").read_text()
    assert "compose.check(" in src and 'S.get("boxes"' in src


def test_a_thing_already_in_its_box_is_left_alone():
    cam = C.Pinhole((0, -2, 0.6), (0, 0, 0.6), 28)
    jar = cube((0.05, 0, 0.6), 0.05)
    r = C.fit(cam.project, jar, (0.2, 0.2, 0.8, 0.8), C.screen_axes(cam, False), keep=True)
    assert r["ok"] and r["offset"] == (0.0, 0.0, 0.0)
