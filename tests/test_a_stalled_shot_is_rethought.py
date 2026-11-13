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
