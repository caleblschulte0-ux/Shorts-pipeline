"""A 3D shot starts from the staging that passes the board, and is held to it before a frame renders (2026-11-26).

The operator: "this needs to be an autonomous system that can pump out 1,000 of these", and of shots that took 4 to
18 judge rounds, "what are we not fixing here? Because clearly something is continuously not getting fixed." Three
parts, each held here on recorded evidence:
  store/shot_plan.py     the shot's plan, written before any shot code, refused when it breaks the recipe
  store/recipe_stage.py  Data and the lens placed from the plan, so the staging has the recipe's shape by construction
  store/recipe_check.py  the board's four stills measured on the staged scene
tests/data3d_recipe/*.json are the FACTS of real stagings, read off their scenes in Blender (recipe_check.collect, no
render): lava shots 3, 4 and 5 as they passed the board, and three stagings the board failed, each with what the
panel said of it. The passed ones must pass; the failed ones must fail for the reason the panel gave."""
import ast
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
STORE = D3 / "store"
sys.path.insert(0, str(STORE))
import recipe_check as RC  # noqa: E402
import recipe_stage as RS  # noqa: E402
import shot_plan as SP  # noqa: E402

FACTS = Path(__file__).resolve().parent / "data3d_recipe"
LAVA = json.loads((D3 / "stories" / "lava" / "script.json").read_text())
LAVA_PLAN = json.loads((D3 / "stories" / "lava" / "plan.json").read_text())
PASSED = (3, 4, 5)          # lava shots that passed the board: 71, 72, 72

# the storyboard and spoken lines of lava shots 3, 4 and 5 as they PASSED, verbatim: the plan is held against these,
# so the session still restaging shots 1 and 2 can change the script without touching this test
LINES = {
    3: ("3 the wall holds (the lava side of the earth wall: its black boulder face towering across the frame behind him, up to its crest and the sky; low on the black lava field, looking at the wall): the driver in his hard hat stands braced in front of the wall as a river of glowing lava comes across the black field at it. It slams into the foot of the boulder face beside him and heaps up, steam rising off it. It stops dead against the rock, its crust going dark, and he pumps his fists and grins at us.",
        "So when the lava came, it hit the wall, and the wall held."),
    4: ("4 the crack (an empty street of town houses inside the wall, the earth wall across its far end; a little above him, looking up the street): the driver in his hard hat walks down the empty street. A zig-zag crack tears open down the middle of the road at his feet, glowing orange, and he staggers back from it, arms flung out; lava wells up out of the crack and runs down the street past the doors of the houses, and he throws a hand up against the heat.",
        "But then the ground split open inside the wall, and lava poured into the streets."),
    5: ("5 the payoff (the morning after in his empty street: his own house beside him with its dark window, a row of saved houses up the street, their windows dark, three houses burning on the black lava slope above them; level with him): three houses burn side by side on the slope above the street, black smoke over them. The driver in his hard hat hangs a lit lantern on the hook by his own dark window. The window lights up warm and he looks round at it. He looks round to us and opens his hands.",
        "Three houses burned. The rest still stand, but almost nobody moved back. Would you?"),
}


def plan(n):
    return copy.deepcopy(LAVA_PLAN["shots"][n - 1])


def problems(p, n):
    return SP.shot_problems(p, LINES[n][0], LINES[n][1], last=n == 5)


def kinds(probs):
    return {p.split(":")[0] for p in probs}


def facts(name):
    return json.loads((FACTS / f"{name}.json").read_text())


# ------------------------------------------------------------------ the plan

@pytest.mark.parametrize("n", PASSED)
def test_the_plans_of_the_shots_that_passed_are_accepted(n):
    assert problems(plan(n), n) == []


def test_fewer_than_four_distinct_events_is_refused():
    p = plan(3); p["stills"] = p["stills"][:3]
    assert "STILLS" in kinds(problems(p, 3))
    p = plan(3); p["stills"][3]["shows"] = p["stills"][2]["shows"]          # the result twice
    assert any("same thing" in x for x in problems(p, 3))
    p = plan(3); p["stills"][2]["new"] = []                                 # a still with nothing new in it
    assert any("names nothing `new`" in x for x in problems(p, 3))


def test_one_pose_scaled_is_not_four_events():
    p = plan(3)
    for s in p["stills"][1:]:
        s["new"] = [{"what": "data", "how": "pose", "cause": "he runs nearer, bigger in the frame"}]
    probs = problems(p, 3)
    assert any("same pose scaled" in x for x in probs), probs
    assert any("one event three times" in x for x in probs), probs
    p = plan(3); p["stills"][1]["new"] = [{"what": "lava river", "how": "bigger", "cause": "the lens pushes in"}]
    assert any("one picture scaled" in x for x in problems(p, 3))


def test_more_than_one_action_is_refused():
    p = plan(4); p["action"] = "he drops a sandbag and leaps back, then a crack tears open and the sandbag falls in"
    assert "ACTION" in kinds(problems(p, 4))
    p = plan(4); p["consequence"] = "lava wells up and the houses catch fire, then the wall falls"
    assert "CONSEQUENCE" in kinds(problems(p, 4))


def test_a_consequence_no_still_shows_is_refused():
    p = plan(5); p["consequence"] = "every house in the street lights up"
    assert "RESULT" in kinds(problems(p, 5))
    p = plan(5); p["stills"][2]["new"] = [{"what": "data", "how": "pose", "cause": "he smiles"}]     # the result is only his face
    assert any("changes no prop" in x for x in problems(p, 5))


def test_a_promise_of_the_texts_that_no_still_shows_is_refused():
    # lava shot 4 through round 7: the line named a sandbag that dropped into the gap, and no still showed it
    line = LINES[4][0] + " The sandbag drops into the gap and catches fire."
    probs = SP.shot_problems(plan(4), line, LINES[4][1])
    assert any(x.startswith("FOR") and "sandbag" in x for x in probs), probs
    probs = SP.shot_problems(plan(5), LINES[5][0], "Seven houses burned. The rest still stand. Would you?")
    assert any(x.startswith("SAYS") and "Seven" in x for x in probs), probs
    p = plan(5); p["says_still"] = None
    assert "SAYS" in kinds(problems(p, 5))


def test_a_wide_establishing_shot_as_the_only_framing_is_refused():
    wide = "2 the wall (the whole valley; wide, from far off in the town): he sets a boulder on the wall."
    assert "FRAMING" in kinds(SP.shot_problems(plan(3), wide, ""))
    p = plan(3); p["framing"] = "wide"
    assert "FRAMING" in kinds(problems(p, 3))
    p = plan(3); p["data"]["frame_h"] = 0.15
    assert "DATA" in kinds(problems(p, 3))
    p = plan(3); p["data"]["stands"] = "far in front, the lava behind him"
    assert "DATA" in kinds(problems(p, 3))


def test_a_prop_with_no_cause_no_parts_or_no_hands_is_refused():
    p = plan(5); p["stills"][1]["new"][0]["cause"] = ""
    assert "CAUSE" in kinds(problems(p, 5))
    p = plan(5); p["props"][0]["built_as"] = "a yellow box"
    assert "LOOK" in kinds(problems(p, 5))
    p = plan(5)
    for s in p["stills"]: s["hands"] = "free"
    assert "HANDS" in kinds(problems(p, 5))                                # the lantern is held and no still has his hands on it
    p = plan(5); p["stills"][1]["hands"] = "bucket"
    assert "HANDS" in kinds(problems(p, 5))
    p = plan(5); p["stills"][2]["new"].append({"what": "sandbag", "how": "falls", "cause": "it drops"})
    assert any("not one of the shot's props" in x for x in problems(p, 5))


def test_every_story_is_planned_or_named_with_its_reason_and_the_list_only_shrinks(tmp_path, monkeypatch):
    stories = sorted(p.name for p in (D3 / "stories").iterdir() if (p / "script.json").exists())
    for s in stories:
        script = json.loads((D3 / "stories" / s / "script.json").read_text())
        if SP.held(s):
            assert SP.problems(s, script) == [], f"{s}: a story staged after the plan has a full plan that passes"
        else:
            assert len(SP.PLAN_BEFORE[s]) > 20, f"{s} is excused with no reason"
            full = SP.load(s)
            assert not (full and all(full["shots"]) and SP.validate(script, full) == []), \
                f"{s} has a full valid plan: take it out of shot_plan.PLAN_BEFORE"
    assert set(SP.PLAN_BEFORE) <= set(stories), "PLAN_BEFORE names a story that is gone"
    # a NEW story with no plan is refused; with a blank one, every shot is refused
    new = tmp_path / "tulips"; new.mkdir()
    monkeypatch.setattr(SP, "STORIES", tmp_path)
    script = {"lines": ["a", "b"], "storyboard": ["1 a (x; close): he does it.", "2 b (x; close): it happens."]}
    assert SP.held("tulips") and any("no stories/tulips/plan.json" in t for _w, t in SP.problems("tulips", script))
    (new / "plan.json").write_text(json.dumps(SP.blank(script)))
    assert {w for w, _t in SP.problems("tulips", script)} == {"shot 1", "shot 2"}


def test_the_lava_plan_on_file_still_fits_its_script():
    for n in PASSED:
        board, says = LAVA["storyboard"][n - 1], LAVA["lines"][n - 1]
        assert SP.shot_problems(plan(n), board, says, last=n == 5) == [], f"shot {n}: its line changed; the plan changes with it"


# ------------------------------------------------------------------ the four stills, measured

@pytest.mark.parametrize("n", PASSED)
def test_the_lava_shots_that_passed_the_board_pass_the_recipe_check(n):
    f = facts(f"lava_head_shot{n}")
    assert RC.problems(f, plan(n)) == [], "a check that fails a shot the board passed is a wrong check"
    assert RC.problems(f, None) == []


def test_shot_2_restaged_along_the_crest_fails_for_what_the_panel_said():
    # 2026-11-26 11:59Z, 38: "the boulder sits on top of his hard hat with neither hand under or on it" (frame 2) and
    # "frame 4: he is turned away from the lens, three-quarter from behind"
    probs = RC.problems(facts("lava_a91a0a528_shot2"))
    assert any(p.startswith("HANDS") and "boulder" in p and "still 2" in p for p in probs), probs
    assert any(p.startswith("FACE") and "still 4" in p for p in probs), probs


def test_the_wide_round_six_restage_fails_for_what_the_panel_said():
    # 2026-11-25 10:15Z, 14: "TINY DATA: frames 1, 2 and 4: Data and the barrow are not in the frame at all"
    probs = RC.problems(facts("lava_483b15222_shot4"))
    assert sum(p.startswith("FRAME") and "not in the frame at all" in p for p in probs) == 3, probs
    assert "CLOSE" in kinds(probs) and "EDGE" in kinds(probs) and "HANDS" in kinds(probs), probs
    # the same round's shot 2, 14: "Frame 1 has Data's head cut off by the left and bottom edges", "BACK TO CAMERA"
    probs = RC.problems(facts("lava_483b15222_shot2"))
    assert any(p.startswith("FRAME") and "still 1" in p for p in probs), probs
    assert sum(p.startswith("FACE") for p in probs) >= 2, probs


def _still(h=0.36, face=20.0, chest=30.0, pose=None, groups=None, frame=1, box=(0.2, 0.15, 0.55, 0.65)):
    pose = pose or {"spine": [0, 0, 1], "arm.L": [1, 0, 0], "arm.R": [-1, 0, 0], "head": [0, 0, 1], "leg.L": [0, 0, -1]}
    return {"at": 0.0, "frame": frame, "cutaway": False, "data": {"h": h, "face_deg": face, "chest_deg": chest, "box": list(box), "pose": pose},
            "groups": groups or {}}


def _group(centre=(1.0, 0.0, 0.3), dims=(0.4, 0.4, 0.5), box=(0.55, 0.3, 0.85, 0.6), hand=0.5, bearing=60.0, drawn=1):
    return {"drawn": drawn, "box": list(box), "all_front": True, "centre": list(centre), "dims": list(dims), "hand_gap": hand, "bearing": bearing, "away": 0.6}


def _facts(stills, groups, conseq=()):
    return {"nf": 120, "fps": 30, "res": [1080, 1920], "stills": stills, "groups": groups, "conseq": list(conseq)}


POSES = [{"spine": [0, 0, 1], "arm.L": [1, 0, 0], "arm.R": [-1, 0, 0], "head": [0, 0, 1]},
         {"spine": [0, 0.3, 0.95], "arm.L": [0, -1, 0], "arm.R": [0, -1, 0], "head": [0, 0.2, 0.98]},
         {"spine": [0, -0.3, 0.95], "arm.L": [0.7, 0, 0.7], "arm.R": [-0.7, 0, 0.7], "head": [0, -0.2, 0.98]},
         {"spine": [0, 0, 1], "arm.L": [0, 0, 1], "arm.R": [0, 0, 1], "head": [0.3, 0, 0.95]}]
PROP = {"prop:crate": {"label": "crate", "whole": True, "kind": "prop", "objects": 1}}
GRIP = {"grip:crate": {"label": "crate", "whole": True, "kind": "grip", "objects": 1}}


def _good(key="prop:crate", groups=PROP):
    """a staging with the recipe's shape: four poses, a crate he carries from one place to another"""
    c = [(1.0, 0.0, 0.3), (1.0, 0.0, 0.3), (1.6, 0.0, 0.3), (1.6, 0.0, 0.3)]
    h = [0.5, 0.02, 0.02, 0.5]
    return _facts([_still(pose=POSES[i], frame=1 + 30 * i, groups={key: _group(centre=c[i], hand=h[i])}) for i in range(4)], groups)


def test_a_staging_with_the_recipes_shape_passes():
    assert RC.problems(_good()) == []
    assert RC.problems(_good("grip:crate", GRIP)) == []


def test_one_pose_only_bigger_is_one_event():
    f = _good()
    for i, s in enumerate(f["stills"]):
        s["data"]["pose"] = POSES[0]; s["data"]["h"] = 0.3 + 0.1 * i; s["groups"]["prop:crate"] = _group()
    probs = RC.problems(f)
    assert sum(p.startswith("EVENTS") and RC.SCALE_ONLY in p for p in probs) == 3, probs
    assert any("no result a viewer can see" in p for p in probs), probs


def test_a_whole_prop_cut_by_the_frame_edge_fails_and_a_field_wide_one_does_not():
    f = _good(); f["stills"][2]["groups"]["prop:crate"]["box"] = [0.8, 0.3, 1.12, 0.6]
    assert any(p.startswith("EDGE") and "[3]" in p for p in RC.problems(f))
    f["groups"] = {"prop:crate": dict(PROP["prop:crate"], whole=False)}
    assert "EDGE" not in kinds(RC.problems(f))


def test_a_prop_that_changes_place_needs_a_cause():
    f = _good()
    for s in f["stills"]: s["groups"]["prop:crate"]["hand_gap"] = 0.6          # it moves and no hand is ever on it
    probs = RC.problems(f)
    assert any(p.startswith("CAUSE") and "stills 2 and 3" in p for p in probs), probs
    f2 = copy.deepcopy(f); f2["conseq"] = [{"key": "prop:crate", "t0": 1.0, "t1": 2.2, "moves": True}]
    assert "CAUSE" not in kinds(RC.problems(f2)), "a consequence that declares it moving then is its cause"
    pl = {"props": [{"name": "crate", "objects": ["crate"]}], "stills": [{"hands": "free"}, {"hands": "free"},
          {"hands": "free", "new": [{"what": "crate", "how": "moves", "cause": "the flood carries it off"}]}, {"hands": "free"}]}
    assert "CAUSE" not in kinds(RC.problems(f, pl)), "the plan's still names the change and its cause"


def test_hands_are_on_what_the_plan_says_and_on_a_grip_that_travels():
    f = _good("grip:crate", GRIP)
    for s in f["stills"]: s["groups"]["grip:crate"]["hand_gap"] = 0.4
    assert any(p.startswith("HANDS") and "floats" in p for p in RC.problems(f))
    f = _good()
    pl = {"props": [{"name": "crate", "objects": ["crate"]}], "stills": [{"hands": "crate"}, {"hands": "crate"}, {"hands": "crate"}, {"hands": "free"}]}
    probs = RC.problems(f, pl)
    assert any(p.startswith("HANDS") and "still 1" in p for p in probs) and not any("still 2" in p for p in probs), probs


def test_the_plans_promises_are_measured_on_the_scene():
    f = _good()
    pl = {"props": [{"name": "crate", "objects": ["crate"]}], "stills": [{"hands": "free"}, {"hands": "free", "new": [{"what": "crate", "how": "moves", "cause": "he shoves it"}]},
          {"hands": "free"}, {"hands": "free"}]}
    assert any(p.startswith("PLAN") and "still 2" in p for p in RC.problems(f, pl)), "it has not moved by still 2"
    f["groups"] = {"prop:crate": dict(PROP["prop:crate"], objects=0)}
    assert any("names no object in the scene" in p for p in RC.problems(f, pl))


def test_close_face_and_frame():
    f = _good()
    for s in f["stills"][:2]: s["data"]["h"] = 0.2
    assert "CLOSE" in kinds(RC.problems(f))
    f = _good(); f["stills"][3]["data"]["face_deg"] = 95.0
    assert "FACE" in kinds(RC.problems(f))
    f = _good()
    for s in f["stills"]:
        s["data"]["chest_deg"] = 5.0; s["groups"]["prop:crate"]["bearing"] = 160.0
    assert any("backdrop" in p for p in RC.problems(f)), "square to the lens with the event behind his back"
    f = _good(); f["stills"][1]["data"]["box"] = [-0.2, 0.1, 0.2, 0.6]
    assert "FRAME" in kinds(RC.problems(f))


# ------------------------------------------------------------------ the staging helper

PROPS = [(0.25, 0.25, 0.3), (0.3, 0.3, 0.4), (0.5, 0.4, 0.6), (0.6, 0.6, 1.6), (0.8, 0.5, 1.1), (1.0, 1.0, 1.0)]


@pytest.mark.parametrize("size", PROPS)
def test_a_staging_from_the_helper_has_the_recipes_shape_by_construction(size):
    for side in SP.SIDES:
        for stands in SP.STANDS:
            for az in (0.0, 70.0, 200.0, 315.0):
                st = RS.stage((3.0, -2.0, 0.1), size, side=side, stands=stands, view_az=az)
                assert st["ok"], (size, side, stands, az, st["why"])
                assert st["frame_h"] >= SP.MIN_FRAME_H and RC.SQUARE_DEG < st["chest_deg"] <= 60 and st["bearing"] < RC.BEHIND_DEG
                b = st["prop_box"]
                assert b[0] >= 0 and b[1] >= 0 and b[2] <= 1 and b[3] <= 1 and b[3] - b[1] >= RS.HERO_MIN_H, (size, b)
                assert (st["face_at"][0] < 0.5) == (side == "left"), "he is on his side of the frame, the prop on the other"
                # and the same staging, as the measured check reads it, on all four stills
                stills = [_still(h=s["data"]["h"], face=s["data"]["face_deg"], chest=s["data"]["chest_deg"], pose=POSES[i], frame=s["frame"],
                                 groups={"prop:it": dict(_group(), **s["prop"], hand_gap=0.02 if i in (1, 2) else 0.5)})
                          for i, s in enumerate(RS.facts(st))]
                stills[2]["groups"]["prop:it"]["centre"] = [9.0, 9.0, 9.0]         # what the action does to it is the shot's own
                stills[3]["groups"]["prop:it"]["centre"] = [9.0, 9.0, 9.0]
                probs = RC.problems(_facts(stills, {"prop:it": {"label": "it", "whole": True, "kind": "prop", "objects": 1}}))
                assert not kinds(probs) & {"CLOSE", "FACE", "EDGE", "FRAME"}, probs


def test_a_prop_too_big_to_be_whole_beside_him_is_refused_with_the_way_out():
    st = RS.stage((0.0, 0.0, 0.0), (8.0, 2.0, 4.0))
    assert not st["ok"] and "whole: False" in st["why"]
    st = RS.stage((0.0, 0.0, 0.0), (40.0, 8.0, 4.0), whole=False, stands="at the foot of", focus=(2.0, -4.2, 0.4))
    assert st["ok"] and st["frame_h"] >= SP.MIN_FRAME_H and st["bearing"] < RC.BEHIND_DEG


def test_the_helper_reads_the_plan_and_gives_four_keys():
    st = RS.from_plan(plan(5), (0.0, 0.0, 0.0), (0.3, 0.3, 0.45))
    assert st["ok"] and st["side"] == "left" and abs(st["frame_h"] - 0.42) < 1e-6
    assert [k["event"] for k in st["keys"]] == list(SP.EVENTS) == list(RS.EVENTS)
    assert [k["at"] for k in st["keys"]] == list(RC.KEYS_AT)
    assert len({k["arms"] for k in st["keys"]}) == 4, "four different poses"
    assert all(st["times"][k["event"]] <= k["at"] for k in st["keys"]), "each event has landed by its still"


def test_a_planned_story_starts_from_a_stub_that_calls_the_recipe():
    src = RS.stub("lava")
    tree = ast.parse(src)
    fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert fns == [f"shot{i}" for i in range(1, 6)]
    assert src.count("recipe_stage.from_plan(") == 5 and src.count("recipe_stage.perform(") == 5 and src.count("recipe_stage.frame(") == 5
    assert "he hangs a lit lantern on the hook" in src, "the plan's action is in the stub"


# ------------------------------------------------------------------ one set of numbers, and it is wired

def _const(path, name):
    for node in ast.parse((STORE / path).read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path} has no {name}")


def test_the_three_modules_and_the_store_agree_on_the_numbers():
    assert tuple(_const("staging.py", "KEYS_AT")) == RC.KEYS_AT == RS.KEYS_AT
    assert _const("staging.py", "HERO_MIN_H") == RS.HERO_MIN_H
    assert _const("staging.py", "MIN_H") <= RC.CLOSE_H <= SP.MIN_FRAME_H == RS.MIN_H, "the recipe is never looser than the store's floor"
    assert RC.FACE_MAX <= _const("staging.py", "KEY_BACK_DEG"), "a check here only ever adds a block"
    assert (RS.SQUARE_DEG, RS.BEHIND_DEG) == (RC.SQUARE_DEG, RC.BEHIND_DEG)
    assert set(RC.MEASURED) == set(SP.HOW_BOX)
    assert all(h >= SP.MIN_FRAME_H for h in RS.HEIGHTS)
    # the helper's sizes are the passing shots' own (compose.frame_data height= in lava shots 3, 4, 5)
    lava = (D3 / "stories" / "lava")
    used = {float(m) for n in PASSED for m in re.findall(r"frame_data\([^\n]*height=([0-9.]+)", (lava / f"shot{n}.py").read_text())}
    assert used and all(min(RS.HEIGHTS) <= h <= max(RS.HEIGHTS) for h in used), used


def test_the_plan_and_the_recipe_check_run_in_the_shot_harness_before_any_frame_renders():
    src = (STORE / "shots.py").read_text()
    code = "\n".join(l for l in src.split('"""', 2)[2].splitlines() if not l.lstrip().startswith("#"))
    plan_at, check_at, render_at = code.index("shot_plan.problems(STORY, SCRIPT)"), code.index("recipe_check.check("), code.index("bpy.ops.render.render")
    built_at = code.index("S = SHOTS[SHOT]()")
    assert plan_at < built_at < check_at < render_at, "the plan before the shot is built, the measured check before a frame renders"
    assert re.search(r"if _pl and os\.environ\.get\(\"STAGING\", \"strict\"\) == \"strict\":\s+raise SystemExit", code)
    assert re.search(r"recipe_check\.check\([^\n]*\\\s+and shot_plan\.held\(STORY\) and os\.environ\.get\(\"STAGING\", \"strict\"\) == \"strict\":\s+raise SystemExit", code)
    assert "plan=shot_plan.shot(STORY, SHOT)" in code
    # the board path (board3d.sh, proof_loop) builds every shot through the harness, strict, before the pre-flight and the panel
    assert "STAGING=strict" in (STORE / "board3d.sh").read_text() and "shots.py" in (STORE / "board3d.sh").read_text()


def test_the_checks_add_blocks_and_touch_no_bar():
    for mod in ("recipe_check.py", "recipe_stage.py", "shot_plan.py"):
        code = (STORE / mod).read_text()
        tree = ast.parse(code)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {"PASS_SCORE", "judge3d", "operator_said", "best_cut"}, mod
        assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and any("judge3d" in (a.name or "") for a in n.names) for n in ast.walk(tree)), mod


def test_the_readme_tells_a_new_story_the_order():
    doc = (D3 / "README.md").read_text()
    order = [doc.index(w) for w in ("store/shot_plan.py", "store/recipe_stage.py", "store/recipe_check.py")]
    assert order == sorted(order), "plan, then the staging helper, then the measured check"
    assert "plan -> validator -> staging helper -> local checks -> pre-flight -> judge" in doc
