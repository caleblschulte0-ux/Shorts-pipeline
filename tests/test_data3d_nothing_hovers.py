"""NOTHING HOVERS (caaleb, 2026-11-14, of the saffron balance: "the scale goes down, but the saffron just hovers in
place. Like little things like that need to get fixed too").

props.pour rested every item at the point it landed, forever. The balance pan then sank as the beam came level and
the heap stayed in the air. Now a rested item rides its support (carry_fn), and pour itself refuses to bake one
left above its surface, so a moving support without carry_fn fails the shot instead of reaching a render."""
import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"


def test_pour_checks_every_rested_item_against_its_surface():
    src = (STORE / "props.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "pour")
    assert "carry_fn" in [a.arg for a in fn.args.args]
    body = ast.unparse(fn)
    assert "raise Floating" in body and "FLOAT_TOL" in body


def test_the_saffron_heap_rides_the_pan():
    src = (ROOT / "tools" / "data3d" / "stories" / "saffron" / "shots.py").read_text()
    assert "carry_fn=lambda t: pan_pt(1, t)" in src


class _O:
    def __init__(self, name): self.name = name; self.location = None; self.keys = {}
    def keyframe_insert(self, what, frame): self.keys.setdefault(what, {})[frame] = tuple(getattr(self, what))
    children_recursive = ()


def _props():
    pytest.importorskip("bpy")
    spec = importlib.util.spec_from_file_location("d3props", STORE / "props.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _sinking(t):           # a pan that drops 6 cm after one second
    return 0.5 - 0.06 * min(1.0, max(0.0, t - 1.0))


def test_a_sinking_support_without_carry_fails():
    P = _props(); from mathutils import Vector
    o = _O("flower")
    with pytest.raises(P.Floating):
        P.pour([o], 60, [0.1], lambda t: Vector((0, 0, 0.7)), lambda x, y, t: _sinking(t))


def test_a_sinking_support_with_carry_takes_the_heap_down():
    P = _props(); from mathutils import Vector
    o = _O("flower")
    P.pour([o], 60, [0.1], lambda t: Vector((0, 0, 0.7)), lambda x, y, t: _sinking(t),
           carry_fn=lambda t: Vector((0, 0, _sinking(t))))
    zs = o.keys["location"]
    assert abs(zs[60][2] - _sinking(59 / 30)) < 0.002
