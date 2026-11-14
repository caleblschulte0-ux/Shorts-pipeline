"""THE STORYBOARD LINT (2026-11-14): a beat's payoff is carried by a BIG prop or action, never by a subtle face or a
tiny change. Every saffron proof that failed the judge had its failure written in its own storyboard first ("the needle
barely twitches", "a wry, unimpressed look"). Held here over every story folder; store/shots.py runs the same lint
before a frame renders. Posted stories are exempt (the same set the ending-question test exempts); a grandfathered
story is named with its reason, and this test fails the day its entry is no longer needed."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import boardlint as BL  # noqa: E402

STORIES = sorted(p for p in (D3 / "stories").iterdir() if (p / "script.json").exists())


def test_a_payoff_on_a_tiny_change_or_a_face_is_flagged():
    for beat in ("he drops the threads on the scale: the needle barely twitches",
                 "Data reacts to the empty shelf",
                 "he looks at us, worried",
                 "the dial moves slightly; he gives us a wry look",
                 "a subtle change in the light"):
        assert BL.beat_problems(beat), beat


def test_a_payoff_carried_by_something_big_passes():
    for beat in ("a whole wall of copies fills behind him; he looks back at us, worried",
                 "the tower of crates topples onto the floor",
                 "he pours a sack of coins into the jar until it overflows",
                 "the needle barely holds as a huge sack crashes onto the pan",
                 "a giant clock's hands race round while the field shuts"):
        assert not BL.beat_problems(beat), (beat, BL.beat_problems(beat))


def test_a_tiny_change_needs_its_carrier_in_the_same_clause():
    """a big prop somewhere else in the beat does not carry 'the needle barely twitches'"""
    beat = "a big white kitchen scale; he drops the threads on its pan: the needle barely twitches"
    assert any(p.startswith("TINY") for p in BL.beat_problems(beat))


def test_every_story_that_is_held_passes_and_the_exemptions_are_honest():
    assert BL.POSTED == {"checkout", "banana"}, "the stories already on the channel (test_data3d_story reads this list)"
    names = {p.name for p in STORIES}
    for st in STORIES:
        probs = BL.problems(json.loads((st / "script.json").read_text()))
        if BL.held(st.name):
            assert not probs, f"{st.name}: {probs}"
        elif st.name in BL.GRANDFATHERED:
            assert probs, f"{st.name} passes the storyboard lint now: delete its GRANDFATHERED entry in store/boardlint.py"
    assert set(BL.GRANDFATHERED) <= names, "a grandfather entry for a story that does not exist"
    assert all(len(why) > 80 for why in BL.GRANDFATHERED.values()), "a grandfathered story says why, and who fixes it"


def test_the_harness_runs_it_before_anything_renders():
    src = (D3 / "store" / "shots.py").read_text()
    assert src.index("import boardlint") < src.index("exec(compile(open(_story)"), "the lint runs before the shot is built"
    assert "boardlint.held(STORY) and boardlint.problems(SCRIPT)" in src
