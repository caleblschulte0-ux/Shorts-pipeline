"""2026-11-18, card rewards (caaleb: "Clearly our issues arnt fixed"): four 20-minute proof rounds failed shots for
what one still showed -- the beat's prop a sliver beside Data's head, a ramp built under the counter -- while the
one-minute still-judge sat unused. Held here: the proof loop judges stills BEFORE any proof render, and the measured
consequence check holds the beat's own prop to a quarter of the frame and refuses parts built under the set."""
import ast, re
from pathlib import Path

STORE = Path(__file__).resolve().parents[1] / "tools" / "data3d" / "store"


def test_the_proof_loop_runs_the_storyboard_before_any_proof():
    src = (STORE / "proof_loop.py").read_text()
    main = src[src.index("for rnd in range(1, a.rounds + 1):"):]
    assert main.index("board(a.story") < main.index("render_proof("), "stills must be judged before a proof renders"
    assert "proof = [n for n in todo if a.no_board or bv.get(n, {}).get(\"pass\")]" in main
    assert "JUDGE3D_BOARD=\"1\"" in src


def test_the_beats_prop_must_fill_a_quarter_of_the_frame():
    src = (STORE / "staging.py").read_text()
    v = float(re.search(r"^HERO_MIN_H = ([0-9.]+)", src, re.M).group(1))
    assert v >= 0.25
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "consequence")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert {"HERO_MIN_H", "FLOOR_Z"} <= names, "the gate constants must be used, not just declared"
