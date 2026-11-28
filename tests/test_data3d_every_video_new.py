"""Every video is new, and every beat is worth watching (caaleb, 2026-11-19, of the rebuilt card rewards short:
"Half that was the Dr. Katz effect. Half of them were reusing backgrounds ... data pumping up a price tag. Like, that
works for maybe 1 second ... Pouring coins into a fucking jar. That's in every single one of our videos.")

store/variety.py looked across the beats of one short; nothing looked across the shorts. store/fresh.py does."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import fresh  # noqa: E402


def _arc(*whats):
    n = len(whats)
    return [{"at": round(0.05 + 0.85 * i / (n - 1), 2), "what": w} for i, w in enumerate(whats)]


GOOD = {
    "lines": ["a", "b", "c", "d", "e"],
    "sets": ["glacier", "ice_cave", "ship_deck", "harbour_town", "lighthouse"],
    "storyboard": ["1 hook: Data rides a cracking ice slab", "2 he hauls a sled", "3 he ropes a mast",
                   "4 he runs the gangway", "5 he lights the beacon"],
    "staging": [
        {"camera": "wide", "data": "rides the slab as it breaks off", "props": ["ice slab"],
         "arc": _arc("crack runs under his boots", "slab tilts, he windmills", "it drops", "he surfs it down to the water")},
        {"camera": "tracking", "data": "hauls the sled", "props": ["sled"],
         "arc": _arc("he digs in", "a runner snags on a rock", "he heaves it free", "he tumbles over the top")},
        {"camera": "low", "data": "ropes the mast", "props": ["mast"],
         "arc": _arc("he throws the rope", "it wraps round the mast", "the sail snaps open", "it lifts him off the deck")},
        {"camera": "profile", "data": "runs the gangway", "props": ["gangway"],
         "arc": _arc("planks fall behind him", "he leaps a gap", "lands on the deck", "the ship pulls away")},
        {"camera": "close", "data": "lights the beacon", "props": ["beacon"],
         "arc": _arc("he strikes the match", "the wick takes", "the lamp blazes", "the beam swings across the harbour")},
    ],
}


def _with(**kw):
    s = json.loads(json.dumps(GOOD)); s.update(kw); return s


def test_a_new_varied_watchable_short_passes():
    assert fresh.problems("new_story", GOOD) == []


def test_the_shorts_made_before_it_are_its_history_not_its_subjects():
    assert not fresh.held("cardrewards") and not fresh.held("checkout") and fresh.held("new_story")


def test_the_store_set_is_used_up():
    p = fresh.problems("new_story", _with(sets=["store"] + GOOD["sets"][1:]))
    assert any("store set" in w for _, w in p)


def test_a_reused_set_may_be_the_one_callback_but_a_banned_gag_never_is():
    s = _with(sets=["store"] + GOOD["sets"][1:], callbacks={"set:store": "the same checkout we opened on, now empty"})
    assert not any("store set" in w for _, w in fresh.problems("new_story", s))
    sb = list(GOOD["storyboard"]); sb[0] = "1 hook: Data pours coins into a glass jar"
    s = _with(storyboard=sb, callbacks={"gag:coins_into_container": "it is the point"})
    assert any("banned" in w for _, w in fresh.problems("new_story", s))


def test_the_named_stock_gags_are_refused():
    for line in ["Data pours his coins into the jar", "he pumps the price tag up like a balloon",
                 "the pile of receipts grows past his head"]:
        sb = list(GOOD["storyboard"]); sb[1] = "2 " + line
        assert any(f"beat 2" == where for where, _ in fresh.problems("new_story", _with(storyboard=sb))), line


def test_a_gag_an_earlier_short_used_is_refused():
    sb = list(GOOD["storyboard"]); sb[2] = "3 the clock spins through the hours"
    assert any("already done" in w for _, w in fresh.problems("new_story", _with(storyboard=sb)))


def test_the_card_rewards_short_would_now_be_refused():
    s = json.loads((D3 / "stories" / "cardrewards" / "script.json").read_text())
    p = fresh.history_problems("cardrewards_again", s) + fresh.watch_problems(s)
    assert any("store set" in w for _, w in p)
    assert any("banned" in w for _, w in p)
    assert any("arc" in w for _, w in p)


def test_one_action_said_three_times_is_one_moment():
    st = json.loads(json.dumps(GOOD["staging"]))
    st[1]["arc"] = _arc("first stroke: the tag swells", "second stroke: the tag swells", "third stroke: the tag swells", "fourth stroke: the tag swells")
    assert any("DIFFERENT" in w for _, w in fresh.watch_problems(_with(staging=st)))


def test_a_beat_must_still_be_building_at_its_end():
    st = json.loads(json.dumps(GOOD["staging"]))
    st[0]["arc"] = [{"at": 0.05, "what": "a"}, {"at": 0.2, "what": "b"}, {"at": 0.35, "what": "c"}]
    assert any("still be building" in w for _, w in fresh.watch_problems(_with(staging=st)))
    st[0]["arc"] = [{"at": 0.05, "what": "a"}]
    assert any("arc" in w for _, w in fresh.watch_problems(_with(staging=st)))


def test_the_dr_katz_look_is_one_beat_at_most():
    st = json.loads(json.dumps(GOOD["staging"]))
    st[0]["camera"] = "medium"
    assert any("Dr. Katz" in w for _, w in fresh.dr_katz_problems(_with(staging=st)))


def test_talking_heads_are_measured_on_the_stills():
    fr = {1: dict(h=0.9, yaw=10), 2: dict(h=1.2, yaw=-5), 3: dict(h=0.5, yaw=0), 4: dict(h=1.1, yaw=90)}
    assert [n for n, _ in fresh.talking_heads(fr)] == [2]


def test_it_is_wired_into_the_shot_harness_the_storyboard_gate_and_the_judge():
    assert "fresh.problems(STORY, SCRIPT)" in (D3 / "store" / "shots.py").read_text()
    assert "fresh.talking_heads(fr)" in (D3 / "store" / "proof_loop.py").read_text()
    bar = (D3 / "store" / "judge3d.py").read_text()
    for need in ("TALKING HEAD", "ONE-SECOND GAG", "STOCK GAG"):
        assert need in bar
    assert "Medium shots and close-ups only" not in bar


# ---- story and world first (caaleb, 2026-11-19: "you just realize you're much more writing a story now. Building a
# world that the viewer has to believe in. And you're just being very, very lazy about it.")
import story_world  # noqa: E402
import variety  # noqa: E402

WORLD = {
    "logline": "A harbour pilot races a storm from the glacier down to his ship before it sails without him.",
    "hero": "Data as the harbour pilot: an orange float coat over his lab coat",
    "goal": "reach his ship before it sails without him",
    "place": "one fjord: a glacier above a town, an ice cave, the harbour, a lighthouse on the point",
    "time": "one afternoon into dusk",
    "weather": "a squall that builds the whole way",
    "path": GOOD["sets"],
    "continuity": {"float coat": "his costume, in every beat", "ship": "his goal: seen in beat 1, reached in beat 4"},
}
STORYBOARD = ["1 the pilot in his float coat rides a cracking slab; his ship waits far below",
              "2 he hauls the sled through the ice cave, coat flapping", "3 he ropes the mast", "4 he runs the gangway onto the ship",
              "5 the pilot lights the beacon"]


def test_a_story_is_planned_as_a_world_first():
    assert story_world.problems("new_story", _with(world=WORLD, storyboard=STORYBOARD)) == []
    assert any("WORLD" in w for _, w in story_world.problems("new_story", GOOD))


def test_the_world_is_his_route_through_one_place():
    w = dict(WORLD, path=list(reversed(GOOD["sets"])))
    assert any("route" in p for _, p in story_world.problems("new_story", _with(world=w, storyboard=STORYBOARD)))


def test_what_the_story_carries_is_seen_in_two_beats():
    w = dict(WORLD, continuity={"brass compass": "his father's"})
    assert any("at least two" in p for _, p in story_world.problems("new_story", _with(world=w, storyboard=STORYBOARD)))


def test_continuity_is_not_a_lazy_reuse_and_spends_no_callback():
    st = json.loads(json.dumps(GOOD["staging"]))
    st[0]["props"] = ["ice slab", "float coat"]; st[3]["props"] = ["gangway", "float coat"]
    assert not any("float coat" in p for _, p in variety.script_problems(_with(staging=st, world=WORLD)))
    assert any("float coat" in p for _, p in variety.script_problems(_with(staging=st)))


def test_the_judge_is_told_whose_story_it_is():
    bar = (D3 / "store" / "judge3d.py").read_text()
    assert "NOT THE WORLD" in bar and '_world.get("logline"' in bar
    assert "story_world.problems(STORY, SCRIPT)" in (D3 / "store" / "shots.py").read_text()
