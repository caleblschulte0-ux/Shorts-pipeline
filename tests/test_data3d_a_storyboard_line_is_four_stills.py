"""A storyboard line is ONE action and ONE consequence, written as what four stills show (2026-11-25). The lava
short's round-7 lines each listed six to eight events and props (a sandbag that vanished, a baton, a hose, a focus
rack) and the board grades four stills against every word; the lines that passed the same day said one action and
one consequence. Held here over the lines themselves, kept verbatim, and over every story folder."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import boardlint as BL  # noqa: E402

STORIES = sorted(p for p in (D3 / "stories").iterdir() if (p / "script.json").exists())

# lava shots 3 and 4 as they PASSED the board on 2026-11-25 (71 and 72), verbatim
PASSED = [
    "3 the wall holds (the lava side of the earth wall: its black boulder face towering across the frame behind him, up to its crest and the sky; low on the black lava field, looking at the wall): the driver in his hard hat stands braced in front of the wall as a river of glowing lava comes across the black field at it. It slams into the foot of the boulder face beside him and heaps up, steam rising off it. It stops dead against the rock, its crust going dark, and he pumps his fists and grins at us.",
    "4 the crack (an empty street of town houses inside the wall, the earth wall across its far end; a little above him, looking up the street): the driver in his hard hat walks down the empty street. A zig-zag crack tears open down the middle of the road at his feet, glowing orange, and he staggers back from it, arms flung out; lava wells up out of the crack and runs down the street past the doors of the houses, and he throws a hand up against the heat.",
]
# the same two shots, and the payoff, as they FAILED through round 7 (commit b22987e5d), verbatim
ROUND_7 = [
    "3 the wall holds (the crest of the earth wall: crushed black rock, the town's coloured roofs below it on the town side, the black lava field on the other; CLOSE, out over the lava a little above his head, AHEAD of him, a medium lens, so we see his face): the lava front, a glowing front of broken black crust with orange in every crack, grinds into the wall's face right under him, its crust blocks heaping up and buckling against the face; the driver in his hard hat braces a fire hose and blasts it, and white steam boils up on both sides of him; the front grinds sideways and slides off along the foot of the wall, away from the town; he follows it with the jet, then lets the nozzle drop and grins at us, steam rolling past.",
    "4 the crack (an empty street of town houses INSIDE the wall, mid-afternoon, the earth wall a dark line at the end of the street with smoke over it; CLOSE at his front right, a medium lens a little below his eye): the driver in his hard hat stands in the empty street with a sandbag in his arms; the road jolts and a zig-zag crack tears across the asphalt right between his boots; he drops the sandbag and leaps back off it; the crack yawns open, glowing orange inside, steam shooting up behind him; the sandbag drops into the gap and catches fire; the lava wells up out of the crack and pours over the road toward us, and he hops back again, arms up against the heat.",
    "5 the payoff (the town's top street at dawn, right under the black lava's edge: a house burning just behind him, flames and smoke pouring off it, the saved houses beside it dark; CLOSE at his front right, a medium lens a little below his eye): the driver in his hard hat hangs a lit lantern on the hook of a black cast-iron bollard, the burning house right behind him, and it swings, glowing; the focus racks past him to the saved houses beside the fire, where a few windows light up, one here, one there, only a handful; he steps toward them, throws both arms up and hops for joy as the lights come on; the focus racks back to him and he turns to us, spreads his hands and shrugs: would you?",
]


def test_the_lines_that_passed_the_board_have_the_shape():
    for line in PASSED:
        assert BL.shape_problems(line) == [], line[:40]
        _, _, _, action = BL.parts(line)
        assert len(BL.events(action)) <= BL.MAX_EVENTS and len(action.split()) <= BL.MAX_WORDS


def test_the_lines_that_failed_seven_rounds_are_refused():
    for line in ROUND_7:
        probs = BL.shape_problems(line)
        assert any(p.startswith("EVENTS") for p in probs), (line[:40], probs)
    assert any(p.startswith("PROP") and "sandbag" in p for p in BL.shape_problems(ROUND_7[1])), "the sandbag that vanished"
    assert any(p.startswith("CAMERA") and "focus racks" in p for p in BL.shape_problems(ROUND_7[2])), "a focus rack is not a still"


def test_the_limits_sit_between_what_passed_and_what_failed():
    """the proxy is measured, not picked: every lava line on the board on 2026-11-25 is under each limit, every
    round-7 line is over the event and the word limit"""
    def measure(line):
        _, _, _, a = BL.parts(line)
        return len(BL.events(a)), len(a.split())
    assert max(measure(l)[0] for l in PASSED) <= BL.MAX_EVENTS < min(measure(l)[0] for l in ROUND_7)
    assert max(measure(l)[1] for l in PASSED) <= BL.MAX_WORDS < min(measure(l)[1] for l in ROUND_7)
    assert BL.MAX_BEATS == 4, "four stills: before, action, result, reaction"


def test_a_line_is_read_as_place_camera_and_action():
    name, place, camera, action = BL.parts(PASSED[0])
    assert name == "the wall holds" and camera == "low on the black lava field, looking at the wall"
    assert place.startswith("the lava side of the earth wall") and action.startswith("the driver in his hard hat")
    assert BL.parts("2 clones (warehouse): a long row of plants; Data walks it")[1:] == ("warehouse", "", "a long row of plants; Data walks it")
    assert BL.parts("no brackets at all")[3] == "no brackets at all"
    assert len(BL.events("the flag climbs past 0.50, 1.00 to 2.17 and stops")) == 1, "a price is not the end of a sentence"


def test_a_prop_that_leaves_his_hands_is_named_in_the_result():
    gone = "1 x (a street; close): he stands with a crate. He drops the crate and jumps back. The road splits and he stares."
    kept = "1 x (a street; close): he stands with a crate. He drops the crate and jumps back. The crate lies split open at his feet."
    assert any(p.startswith("PROP") and "crate" in p for p in BL.shape_problems(gone))
    assert BL.shape_problems(kept) == []
    assert BL.shape_problems("1 x (a street; close): the road cracks and he throws a hand up against the heat.") == [], "a pose is not a prop"
    assert BL.shape_problems("1 x (a street; close): he staggers back and throws his arms wide.") == []


def test_the_camera_is_said_once_and_never_moves_inside_the_action():
    for bad in ("he lifts the jar and the camera pulls back over the town", "the wall holds; cut to the street below",
                "he grins as we zoom in on the crack", "the lens cranes up over the row"):
        assert any(p.startswith("CAMERA") for p in BL.shape_problems(f"1 x (a street; close): {bad}.")), bad
    assert BL.shape_problems("1 x (a field; low, close to the flowers): one big crocus close to the camera wilts and flops over.") == []


def test_every_story_that_is_held_has_the_shape_and_the_exemptions_are_honest():
    names = {p.name for p in STORIES}
    for st in STORIES:
        probs = BL.shape(json.loads((st / "script.json").read_text()))
        if BL.shape_held(st.name):
            assert not probs, f"{st.name}: {probs}"
        elif st.name in BL.SHAPE_BEFORE:
            assert probs, f"{st.name} has the shape now: delete its SHAPE_BEFORE entry in store/boardlint.py"
    assert set(BL.SHAPE_BEFORE) <= names, "an exemption for a story that does not exist"
    assert all(len(why) > 80 for why in BL.SHAPE_BEFORE.values()), "an exempt story says why, and who fixes it"
    assert BL.shape_held("lava") and BL.shape_held("honey")


def test_the_harness_refuses_to_build_a_line_without_the_shape():
    src = (D3 / "store" / "shots.py").read_text()
    assert src.index("boardlint.shape(SCRIPT)") < src.index("exec(compile(open(_story)"), "the shape is checked before the shot is built"
    assert "boardlint.shape_held(STORY) and _shape" in src


def test_the_staging_that_passes_is_given_to_whoever_writes_and_restages_a_shot():
    for must in ("BEFORE", "RESULT", "REACTION", "CLOSE", "beside him or in front of him, mid-frame", "touches a frame edge",
                 "three-quarter to the lens", "clearly different", "one grade", "feet are planted", "every prop the line names"):
        assert must in BL.RECIPE, must
    readme = " ".join((D3 / "README.md").read_text().split())
    for row in BL.RECIPE.splitlines()[1:]:
        assert " ".join(row.lstrip("- ").split()) in readme, f"the README's recipe is the lint's, word for word: {row}"
    sys.argv = ["proof_loop.py"]
    import proof_loop as P
    assert "{recipe}" in P.REVISER
    src = (D3 / "store" / "proof_loop.py").read_text()
    assert "recipe=boardlint.RECIPE" in src[src.index("def revise("):]
