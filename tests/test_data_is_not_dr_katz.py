"""DATA ACTS WITH HIS WHOLE BODY, AND TALKS LIKE A PERSON (caaleb, 2026-11-13, of the first acting clip: "had a bit of
a dr.Katz effect but the idea is right"). Measured on that clip: in every held pose the body moved 0.2 (mean frame
difference) -- frozen -- while the mouth flapped open and shut every 0.07 s, all one size. A stiff body with a flapping
mouth IS that look. Held here without Blender (the functions are read out of character.py):
  - a spoken line is syllables of uneven length and size, in phrases with breaths between, never a 0.07 s flap
  - every held performance keeps living (perform() calls alive())
  - talking moves the head on the stressed word (talk() keys the neck and head)"""
import ast
import random
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "tools" / "data3d" / "character.py").read_text()
TREE = ast.parse(SRC)


def _fn(name, tree=TREE):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"character.py has no {name}()")


def _syllables():
    ns = {}
    exec(compile(ast.Module(body=[_fn("syllables")], type_ignores=[]), "character.py", "exec"), ns)
    return ns["syllables"]


def test_a_line_is_syllables_not_a_flap():
    syl = _syllables()
    for seed in range(20):
        s = syl(0.0, 4.0, seed=seed)
        durs = [d for _, d, _, _ in s]
        assert min(durs) >= 0.15, "a syllable shorter than 0.15 s is a flap"
        assert max(durs) - min(durs) >= 0.08, "every syllable the same length is a metronome"
        sizes = [v for _, _, v, _ in s]
        assert max(sizes) - min(sizes) >= 0.15, "every syllable the same size"
        gaps = [b[0] - (a[0] + a[1]) for a, b in zip(s, s[1:])]
        assert any(g >= 0.2 for g in gaps), "no breath between phrases"
        assert any(st for *_, st in s), "no stressed syllable"
        assert s[-1][0] + s[-1][1] <= 4.0 + 1e-9


def test_a_held_pose_keeps_living_and_talking_moves_the_head():
    perform = ast.unparse(_fn("perform"))
    assert "self.alive(" in perform, "perform() holds a frozen pose"
    talk = ast.unparse(_fn("talk"))
    assert "'neck'" in talk and "'head'" in talk, "talk() moves only the mouth"
    assert "syllables(" in talk
    alive = ast.unparse(_fn("alive"))
    assert all(b in alive for b in ("'chest'", "'neck'", "'head'"))
