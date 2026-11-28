"""Build fresh, reuse is rare (caaleb, 2026-11-18, of the card rewards 3D short: "That was dog shit on so many levels.
My biggest issue is that it was lazy as shit ... reusing stuff should be like a wow, crazy one-time and forever event,
not we try to reuse everything as much as possible").

That short put Data centred behind a counter in all five beats, one lens, the same gold card in four of them, the same
counter in all five, the store set twice, and had him WATCH while coins moved by themselves. Every per-shot check
passed it. store/variety.py looks across the beats; these tests hold it."""
import ast
import json
import sys
from pathlib import Path

D3 = Path(__file__).resolve().parents[1] / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import variety  # noqa: E402

GOOD = {
    "lines": ["a", "b", "c", "d", "e"],
    "sets": ["store", "kitchen", "bank", "stockroom", "crossroads"],
    "staging": [
        {"camera": "low", "data": "stuffs bills into the register", "props": ["register", "tube"]},
        {"camera": "profile", "data": "pumps the tag up", "props": ["pump", "tag balloon"]},
        {"camera": "high", "data": "shovels coins across", "props": ["shovel", "coin bins"]},
        {"camera": "wide", "data": "cranks the belt", "props": ["conveyor", "vault"]},
        {"camera": "close", "data": "flips the coin", "props": ["giant coin"]},
    ],
}


def _with(**kw):
    s = json.loads(json.dumps(GOOD)); s.update(kw); return s


def test_a_varied_short_passes():
    assert variety.script_problems(GOOD) == []


def test_the_same_camera_back_to_back_is_one_shot():
    st = json.loads(json.dumps(GOOD["staging"])); st[1]["camera"] = "low"
    assert any("twice in a row" in p for _, p in variety.script_problems(_with(staging=st)))


def test_five_beats_need_four_camera_kinds():
    st = json.loads(json.dumps(GOOD["staging"]))
    for b, c in zip(st, ["close", "medium", "close", "medium", "close"]): b["camera"] = c
    assert any("camera kinds" in p for _, p in variety.script_problems(_with(staging=st)))


def test_data_does_the_thing_he_does_not_watch_it():
    st = json.loads(json.dumps(GOOD["staging"])); st[1]["data"] = "watches the tag"; st[3]["data"] = "looks at us"
    assert any("only watches" in p for _, p in variety.script_problems(_with(staging=st)))


def test_a_prop_in_two_beats_is_the_one_callback():
    st = json.loads(json.dumps(GOOD["staging"])); st[4]["props"] = ["giant coin", "register"]
    assert any("'register'" in p for _, p in variety.script_problems(_with(staging=st)))
    assert variety.script_problems(_with(staging=st, callbacks={"register": "the till he started at"})) == []
    assert any("callbacks" in w for w, _ in variety.script_problems(
        _with(staging=st, callbacks={"register": "x", "pump": "y"})))


def test_a_set_twice_is_reuse_too():
    assert any(w == "sets" for w, _ in variety.script_problems(_with(sets=["store", "bank", "store", "kitchen", "dock"])))


SRC = '''
def counter(name):
    SK.table(name, (0, 0, 0))
def schedule(n): return []
def shot1():
    counter("a"); CK.card("c", (0, 0, 0)); schedule(3)
def shot2():
    counter("b"); CK.piggy("p", (0, 0, 0)); schedule(3)
def shot3():
    CK.card("c", (0, 0, 0))
'''


def test_a_builder_in_two_shots_is_reuse_in_code():
    bad = {p.split()[0] for _, p in variety.code_problems(SRC, {})}
    assert bad == {"CK.card", "counter"}, bad          # the timing helper is not a builder
    assert {p.split()[0] for _, p in variety.code_problems(SRC, {"callbacks": {"CK.card": "why"}})} == {"counter"}


def test_two_beats_framed_alike_are_one_shot():
    a = dict(x=0.5, y=0.62, h=0.9, yaw=2.0, pitch=4.0)
    assert variety.framing_problems({1: a, 2: dict(a, x=0.52)})[0][0] == 2
    assert variety.framing_problems({1: a, 2: dict(a, yaw=80.0)}) == []
    assert variety.framing_problems({1: a, 2: dict(a, h=0.4)}) == []


def test_every_held_story_is_varied():
    for st in sorted((D3 / "stories").iterdir()):
        if not (st / "script.json").exists() or not variety.held(st.name): continue
        s = json.loads((st / "script.json").read_text())
        assert variety.script_problems(s) == [], (st.name, variety.script_problems(s))
        assert variety.code_problems((st / "shots.py").read_text(), s) == [], (st.name, variety.code_problems((st / "shots.py").read_text(), s))


def test_it_is_wired_into_the_harness_and_the_storyboard_gate():
    shots = (D3 / "store" / "shots.py").read_text()
    assert "variety.script_problems" in shots and "variety.code_problems" in shots and "staging.framing" in shots
    tree = ast.parse((D3 / "store" / "proof_loop.py").read_text())
    board = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "board")
    assert "framing_problems" in ast.unparse(board)
