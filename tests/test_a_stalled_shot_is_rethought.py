"""A shot the judge keeps failing for the same thing is RETHOUGHT, not polished (caaleb, 2026-11-13: "we can't take
4 days to make one video"). The banana hook spent ~20 rounds polishing a floor stain the judge called a spill every
time; it passed once the stain was cut. And the proof loop never leaves an unjudged edit in shots.py."""
import ast, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "data3d" / "store"))
import proof_loop as pl  # noqa: E402


def test_a_rising_score_is_not_stalled():
    assert not pl.stalled([55, 60], 2)
    assert not pl.stalled([55, 60, 64], 2)


def test_two_revisions_without_a_new_best_is_stalled():
    assert pl.stalled([62, 58, 61], 2)
    assert pl.stalled([64, 64, 63], 2)


def test_the_element_the_judge_keeps_naming_is_found():
    rounds = [["the floor stain reads as a spill"], ["a dark spill under his feet"], ["the stain looks like a puddle"]]
    words = [w for w, c, _ in pl.recurring(rounds)]
    assert "stain" in words and "spill" in words


def test_the_loop_ends_on_the_best_judged_take():
    src = (Path(pl.__file__)).read_text()
    main = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.unparse(main)
    assert "rnd == a.rounds" in body                       # no revision after the last judging round
    assert "put_shot(path, n, best[n][1])" in body.split("for rnd in")[-1].split("return 2")[-2]


def test_a_reshoot_renders_only_the_named_shots(tmp_path):
    """A fix to two shots re-renders two shots: reuse_run + reshoot in the render trigger (caaleb 11-13)."""
    import json, os, subprocess
    narr = tmp_path / "narr.json"
    narr.write_text(json.dumps({"windows": [[0.2, 3.0], [3.2, 6.0], [6.2, 9.0], [9.2, 12.0], [12.2, 15.0]]}))
    log = tmp_path / "shots.log"
    fake = tmp_path / "fakepy"
    fake.write_text(f"#!/bin/sh\necho $SHOT >> {log}\n"); fake.chmod(0o755)
    rr = Path(pl.__file__).with_name("render_range.py")
    env = dict(os.environ, NARR=str(narr), VBPY=str(fake), RESHOOT="3 4")
    subprocess.run([sys.executable, str(rr), "1", "500", str(tmp_path), "8", "30"], env=env, check=True, capture_output=True)
    assert log.read_text().split() == ["3", "4"]


def test_smoothing_keeps_a_held_pose_and_softens_a_step():
    """character._gauss: the twitch filter. A held value stays put; a one-frame step becomes a ramp over several."""
    import importlib.util, types
    src = (Path(pl.__file__).resolve().parents[1] / "character.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_gauss")
    ns = {"math": __import__("math")}
    exec(compile(ast.Module([fn], []), "character.py", "exec"), ns)
    g = ns["_gauss"]
    assert all(abs(x - 1.0) < 1e-9 for x in g([1.0] * 20, 2.0))
    out = g([0.0] * 10 + [1.0] * 10, 1.5)
    steps = [b - a for a, b in zip(out, out[1:])]
    assert max(steps) < 0.35                       # no single frame carries the whole jump
