"""caaleb, 2026-11-23, of the honey storyboard: why were such basic things made at all? Because no check could see
them. Each test here holds a system check (store/staging.py, run strict by store/shots.py on every shot) that
measures one HARD note the board judge had to catch by eye."""
import ast
from pathlib import Path

STORE = Path(__file__).resolve().parents[1] / "tools" / "data3d" / "store"
SRC = (STORE / "staging.py").read_text()
HARNESS = (STORE / "shots.py").read_text()


def _fn(name):
    tree = ast.parse(SRC)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"staging.{name} is missing")


def _cut_off():
    """the pure rule, lifted out of staging.py (which needs bpy) and run here"""
    ns = {}
    exec(compile(ast.Module(body=[_fn("cut_off")], type_ignores=[]), "staging.cut_off", "exec"), ns)
    return ns["cut_off"]


def test_words_half_out_of_the_frame_are_cut():
    cut = _cut_off()
    assert cut((0.85, 0.7, 1.08, 0.8))           # the sign off the right edge (shot 1, round 1)
    assert cut((-0.04, 0.2, 0.2, 0.3))
    assert cut((0.3, 0.95, 0.6, 1.02))           # over the top
    assert not cut((0.1, 0.1, 0.9, 0.9))         # whole in frame
    assert not cut((1.1, 0.1, 1.3, 0.2))         # wholly out of frame is not seen, not cut


def test_every_check_runs_strict_on_every_shot():
    for call in ("staging.edges(", "staging.keys(", "staging.talking(", "staging.cause(", "compose.check("):
        assert call in HARNESS, call
    i = HARNESS.index("_sysok = [")
    assert "raise SystemExit" in HARNESS[i:i + 1500] and '"strict"' in HARNESS[i:i + 1500]


def test_the_edge_check_reads_words_and_his_body_at_the_beat_end():
    body = ast.get_source_segment(SRC, _fn("edges"))
    assert "_texts(" in body and "cut_off(" in body and "CUT_GRACE_S" in body
    assert "sc.frame_set(nf)" in body and "pose.bones" in body
    assert '"FONT"' in ast.get_source_segment(SRC, _fn("_texts")) and "sign" in SRC and "label" in SRC


def test_the_four_board_stills_must_differ():
    body = ast.get_source_segment(SRC, _fn("keys"))
    assert "KEYS_AT" in body and "KEY_DATA" in body and "_news(" in body and "KEY_RIDE" in SRC
    assert "(0.08, 0.38, 0.68, 0.98)" in SRC     # the stills board3d.sh shows the judge


def test_a_talking_head_is_measured_not_declared():
    """fresh.talking_heads only knew a close-up; honey shot 2 was whole, centred, facing us and doing nothing"""
    body = ast.get_source_segment(SRC, _fn("talking"))
    for k in ("TALK_FACE", "TALK_CENTRE", "TALK_HANDS", "TALK_WALK", "_grip_objs("):
        assert k in body, k


def test_nothing_moves_without_his_hand_on_its_cause():
    body = ast.get_source_segment(SRC, _fn("cause"))
    assert "\"moves\"" in body and "CAUSE_BEFORE" in body and "HAND_ON" in SRC
    assert "held + mv" in body and "_working(" in body   # a grip that moves with the work, or the moving part itself


def test_a_shot_is_built_in_the_portrait_frame():
    """the 16:9 default resolution was in force while a shot was BUILT, so compose.drop_cut measured a frame twice as
    wide as the real one and dropped nothing that staging.edges then failed (honey shots 3 and 4)"""
    i = HARNESS.index("S = SHOTS[SHOT]()")
    before = HARNESS[:i]
    assert "resolution_x, sc.render.resolution_y = 1080, 1920" in before[-400:]


def test_a_thing_keyed_off_is_off():
    """a lamp keyed to scale 1e-3 reads 0.0010000000475 as float32: a `> 1e-3` test called it lit, so the FAIL lamp
    coming on between two key stills was not news (honey shot 3)"""
    import struct
    off = struct.unpack("f", struct.pack("f", 1e-3))[0]
    assert off > 1e-3
    cut = float(SRC.split("HIDDEN_SCALE =")[1].split()[0])
    assert off < cut <= 0.05
    state = ast.unparse(_fn("_state"))
    assert "HIDDEN_SCALE" in state and "1e-3" not in state
    assert "HIDDEN_SCALE" in ast.unparse(_fn("_screen_box"))


def test_a_thing_that_lights_under_his_hand_is_news():
    """the FAIL lamp sits by his hand at the test: news is checked BEFORE the rides-with-him rule, and only a thing near
    his hands at BOTH stills rides"""
    news = ast.unparse(_fn("_news"))
    assert news.index("l0 != l1") < news.index("r0 and r1")
    assert "r0 or r1" not in news


def test_a_sign_over_his_head_is_caught():
    """honey board round 2: the 2 EUROS sign "cuts off the top of his head" in three stills, with every check green"""
    ns = {}
    exec(compile(ast.Module(body=[_fn("_overlap")], type_ignores=[]), "staging._overlap", "exec"), ns)
    ov = ns["_overlap"]
    head = (0.5, 0.6, 0.7, 0.8)
    assert ov((0.0, 0.7, 1.0, 1.0), head) >= 0.5        # a sign across the top of his head
    assert ov((0.0, 0.85, 1.0, 1.0), head) == 0.0       # a sign above him
    edges = ast.unparse(_fn("edges"))
    assert "_head_box(" in edges and "_nearer(" in edges and "OVER_HEAD" in edges


def test_every_key_still_shows_his_face():
    """a turn shorter than the 0.35 s back-turned rule still lands on a board still: each still is judged alone"""
    keys = ast.unparse(_fn("keys"))
    assert "KEY_BACK_DEG" in keys and "face_dir(" in keys and "not back" in keys
