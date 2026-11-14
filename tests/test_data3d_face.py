"""DATA'S FACE: every expression is its own face, a one-sided face exists, and a face that is not a smile never turns
into one (2026-11-14). Held offline, with no Blender: the expression table is read out of character.py, and the face
lint's logic (store/facelint.py) is exercised on synthetic frames. tests/test_data3d_rig.py holds the same on the rig.

  - EXPRESSIONS MUST DIFFER: rendered side by side the faces were "nearly one face" (caaleb, 2026-11-13). Each must sit
    at least MIN_APART from neutral and from every other face over what a viewer can SEE of it (below).
  - ONE-SIDED FACE: 'wry' is skeptical: one brow cocked up, the mouth pulled to one side, no smile.
  - FACE LINT: tonight a worried face's release keyed his resting smile inside the next 'alarmed', and the alarm
    turned into a smile. The lint fails a shot on that whole class, and shots.py runs it beside twitch."""
import ast
import itertools
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path[:0] = [str(D3), str(D3 / "store")]
import facelint as FL  # noqa: E402

SRC = (D3 / "character.py").read_text()
TREE = ast.parse(SRC)
CLS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "Data")


def _cls_value(name):
    node = next(n for n in CLS.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name)
    return eval(compile(ast.Expression(node.value), "character.py", "eval"), {"dict": dict})


EXPR = _cls_value("EXPRESSIONS")
NOT_SMILING = _cls_value("NOT_SMILING")
MIN_APART = 0.6


def seen(e):
    """what a viewer can see of a face, each channel on a 0..1 scale of how far it visibly moves. The brow travels only
    0..0.4 of its parameter, so its height counts 2.5x; the glasses frame hides the top and bottom ~30 deg of each eye,
    so a lid counts only past 0.3 of its travel (character.py: "a lid under ~0.35 is never SEEN")."""
    g = lambda k: e.get(k, 0.0)
    lower = min(0.95, g("lid") * 0.6 + g("squint") * 0.8)
    return [g("smile"), g("open"), g("frown"), g("grin"), abs(g("side")), g("brow") * 2.5, g("worry"), g("mad"),
            abs(g("cock")), max(0.0, g("lid") - 0.3) / 0.7, max(0.0, lower - 0.3) / 0.65]


def apart(a, b):
    return math.dist(seen(a), seen(b))


def test_every_expression_is_its_own_face():
    assert "neutral" in EXPR
    close = [(a, b, round(apart(EXPR[a], EXPR[b]), 2)) for a, b in itertools.combinations(EXPR, 2) if apart(EXPR[a], EXPR[b]) < MIN_APART]
    assert not close, f"faces a viewer could not tell apart (need >= {MIN_APART}): {close}"


def test_the_metric_would_have_failed_the_faces_before_this_fix():
    """the bar bites: three pairs of the 2026-11-13 table sat under it"""
    old = {"worried": dict(brow=0.1, lid=0.35, frown=1.0, worry=1.0), "sad": dict(lid=0.62, frown=0.8, worry=0.9),
           "surprised": dict(open=0.75, brow=0.32, frown=0.3, worry=0.25), "alarmed": dict(open=0.55, brow=0.34, frown=0.7, worry=0.55)}
    assert apart(old["worried"], old["sad"]) < MIN_APART and apart(old["surprised"], old["alarmed"]) < MIN_APART


def test_wry_is_one_sided_and_skeptical_not_a_smile():
    w = EXPR["wry"]
    assert abs(w.get("cock", 0)) >= 0.8, "wry raises ONE brow"
    assert abs(w.get("side", 0)) >= 0.6, "wry pulls the mouth to one side"
    assert w.get("smile", 0) == 0 and w.get("grin", 0) == 0
    assert "wry" in NOT_SMILING
    assert not any(e.get("cock") or e.get("side") for k, e in EXPR.items() if k != "wry"), "only wry is lopsided"


def test_the_rig_has_the_one_sided_controls_without_touching_his_shape():
    face = next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "_face")
    args = [a.arg for a in face.args.args]
    assert "cock" in args and "side" in args
    mk = re.search(r"^MOUTH_KEYS = \((.*)\)$", SRC, re.M).group(1)
    assert "'side_R'" in mk and "'side_L'" in mk
    build = ast.unparse(next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "_build"))
    assert build.count("for key in MOUTH_KEYS") == 3, "the lips, the inside of the mouth and its drivers all carry the side keys"
    assert "BROW_SIDE" in build, "each brow knows its side"
    state = ast.unparse(next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "_face_state"))
    assert "cock=" in state and "side=" in state, "the twitch check and expression() read the one-sided controls back"


def test_the_non_smiling_faces_are_the_operators_list():
    assert set(NOT_SMILING) == {"worried", "alarmed", "surprised", "sad", "wry", "determined"}
    for k in NOT_SMILING:
        assert EXPR[k].get("smile", 0) <= FL.SMILE_MAX / 2 and EXPR[k].get("grin", 0) == 0, k


# ---------------------------------------------------------------- the lint's own logic, on synthetic frames
def _paths(rest_up=0.07, smile_up=0.16, frown_up=-0.055):
    """flat stand-ins for character._mouth_paths: a top lip of 3 points (corner, middle, corner) and a bottom of 3"""
    row = lambda up: [(-1, 0, up), (0, 0, 0.0), (1, 0, up), (1, 0, -0.1), (0, 0, -0.1), (-1, 0, -0.1)]
    return {"rest": row(rest_up), "smile": row(smile_up), "frown": row(frown_up), "open": row(-0.17)}


CO = FL.coeffs(_paths(), ("smile", "frown", "open"))


def test_the_smile_read_is_the_mouths_upturn_in_resting_smiles():
    assert abs(FL.smile_read({}, CO) - 1.0) < 1e-9, "his resting face IS a small smile"
    assert FL.smile_read({"frown": 1.0}, CO) < 0
    assert FL.smile_read({"smile": 1.0}, CO) > 2


def test_the_lint_catches_tonights_defect():
    """worried 0..2 s, alarmed from 2.05 s, and the worried face's release keying the rest face at 2.3 s"""
    nf = 120
    log = [("worried", -0.3, 0.0, 2.0, 0.3), ("alarmed", 1.95, 2.05, None, 0.1)]
    states = []
    for f in range(1, nf + 1):
        t = (f - 1) / 30
        states.append({"frown": 1.0} if t < 2.05 else ({} if 2.25 < t < 2.9 else {"frown": 0.85, "open": 0.5}))
    rows, bad = FL.lint(log, states, NOT_SMILING, CO)
    assert bad and all(b[0] == "alarmed" and b[2] == "smile read" for b in bad)
    assert min(b[1] for b in bad) >= FL.F(2.25)
    fixed = [s if s else {"frown": 0.85, "open": 0.5} for s in states]
    assert not FL.lint(log, fixed, NOT_SMILING, CO)[1]


def test_a_later_face_owns_its_frames_and_a_happy_window_is_not_linted():
    log = [("alarmed", -0.1, 0.0, None, 0.1), ("happy", 1.9, 2.0, 2.5, 0.2)]
    own = {name: frames for _, name, frames in FL.owned(log, 120)}
    assert own["happy"] and not set(own["happy"]) & set(own["alarmed"])
    states = [{"smile": 1.0} if 1.9 <= (f - 1) / 30 <= 2.7 else {"frown": 1.0} for f in range(1, 121)]
    assert not FL.lint(log, states, NOT_SMILING, CO)[1], "a smile in a happy window is not a defect"


def test_the_lint_runs_on_every_shot_beside_twitch_and_proof_loop_reads_it():
    shots = (D3 / "store" / "shots.py").read_text()
    assert shots.index("import facelint") > shots.index("import twitch")
    assert "facelint.check(data, NF" in shots and 'raise SystemExit(f"shot {SHOT} fails the face lint' in shots
    assert "FACE" in re.search(r"^CHECKS = re.compile\((.*)\)$", (D3 / "store" / "proof_loop.py").read_text(), re.M).group(1)
    exp = ast.unparse(next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "expression"))
    assert "self.face_log.append(" in exp and "self._clear_face(" in exp and "self._rekey_releases()" in exp


def test_a_release_lets_go_into_the_face_that_holds_the_moment():
    """the banana hook's 'happy' and 'surprised' released to rest in the middle of an open-ended 'alarmed'"""
    rel = ast.unparse(next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "_release_face"))
    assert "'neutral'" in rel and "best = j" in rel
    exp = ast.unparse(next(n for n in CLS.body if isinstance(n, ast.FunctionDef) and n.name == "expression"))
    assert "EXPRESSIONS['neutral']" not in exp, "expression() no longer releases straight to rest"

