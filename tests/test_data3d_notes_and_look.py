"""A judge's note is followed until a round is run AGAINST it, and every judge grades against caaleb's whole look
(2026-11-22: "when you get told what you're trying to go for, you fucking ignore it"). The lightning opening was named
NOT THE WORLD in seven rounds and nothing was ever done about it; the next idea was scored against a rewritten
storyboard and the note went on standing under it. Offline, no Blender, no judge."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
import look_bible  # noqa: E402
import notes_ledger as L  # noqa: E402


@pytest.fixture
def story(tmp_path, monkeypatch):
    (tmp_path / "ridge").mkdir()
    monkeypatch.setattr(L, "STORIES", tmp_path)
    return "ridge"


def _fail(shot, *hard):
    return {"shot": shot, "pass": False, "hard": list(hard)}


def test_a_hard_line_is_tagged_by_the_defect_it_opens_with():
    assert L.tag("NOT THE WORLD, frames 1-36: no narrow crest") == "NOT THE WORLD"
    assert L.tag("HARD: BROKEN: a pop at frames 12-13") == "BROKEN"
    assert L.tag("hard (one judge only): ONE SECOND GAG: it repeats") == "ONE-SECOND GAG"
    assert L.tag("NOT THE POINT / CONSEQUENCE, all frames") == "NOT THE POINT"
    assert L.tag("the sky looks odd") is None


def test_a_note_named_twice_blocks_the_next_panel_until_a_fix_is_written(story):
    L.record(story, [_fail(1, "NOT THE WORLD: no drop")])
    assert L.gate(story, [1]) == []                      # once is a note, not yet a pattern
    L.record(story, [_fail(1, "NOT THE WORLD: still no drop")])
    assert any("NOT THE WORLD" in p for p in L.gate(story, [1]))
    with pytest.raises(SystemExit):
        L.fix(story, 1, "NOT THE WORLD", "fixed")        # a word is not a fix
    L.fix(story, 1, "NOT THE WORLD", "lens moved beside him so the drop and the valley are in frame")
    assert L.gate(story, [1]) == []
    L.record(story, [_fail(1, "NOT THE WORLD: the drop is still not seen")])
    assert L.gate(story, [1]), "a fix that did not work leaves the note open again"


def test_a_new_idea_does_not_wipe_a_note(story):
    """the note is keyed on the shot and the defect, never on what the shot was trying to be"""
    L.record(story, [_fail(1, "NOT THE WORLD: a patio, not a ridge")])
    L.record(story, [_fail(1, "NOT THE WORLD: a stage backdrop behind the tally board")])
    assert "NOT THE WORLD" in L.repeated(story, 1)


def test_a_pass_closes_the_shot_and_other_shots_are_their_own(story):
    for _ in range(2):
        L.record(story, [_fail(1, "BROKEN: pop"), _fail(2, "TALKING HEAD: parked")])
    L.record(story, [{"shot": 1, "pass": True, "hard": []}])
    assert L.gate(story, [1]) == []
    assert L.gate(story, [2])


def test_the_judges_are_shown_the_note_and_the_claimed_fix(story):
    for _ in range(2):
        L.record(story, [_fail(3, "NOT THE WORLD: no valley")])
    L.fix(story, 3, "NOT THE WORLD", "added the pine slope and the lit valley below the crest")
    text = L.for_judge(story, 3)
    assert "NOT THE WORLD" in text and "pine slope" in text and "name it again" in text


def test_judge3d_gates_on_the_ledger_and_records_every_panel():
    src = (STORE / "judge3d.py").read_text()
    assert "notes_ledger.gate(story, only)" in src
    assert "notes_ledger.record(story, v[\"shots\"])" in src
    assert "notes_ledger.for_judge(story, n)" in src
    assert src.index("notes_ledger.gate(story, only)") < src.index("subprocess.Popen(cmd")


def test_every_judge_gets_the_whole_look_and_the_approved_frames():
    env = dict(os.environ, STORY="lightning")
    out = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import judge3d; print(judge3d.BAR)" % str(STORE)],
                         capture_output=True, text=True, env=env, check=True).stdout
    assert "THE OPERATOR'S LOOK" in out and "OFF THE LOOK" in out
    for _, rule, _, said in look_bible.RULINGS:
        assert rule in out and said in out
    assert out.index("THE OPERATOR'S LOOK") < out.index("NOTES: everything else")


def test_every_ruling_has_a_date_and_his_words():
    assert len(look_bible.RULINGS) >= 15
    for area, rule, when, said in look_bible.RULINGS:
        assert area in {"look", "world", "staging"} and len(when) == 10 and when.startswith("2026-") and said.strip()
    assert all(n.endswith(".jpg") for n, _ in look_bible.REFERENCES)


def test_the_lightning_ledger_carries_its_history():
    led = json.loads((ROOT / "tools" / "data3d" / "stories" / "lightning" / L.NAME).read_text())
    assert len({x["round"] for x in led["shots"]["1"]["NOT THE WORLD"]["named"]}) >= 5


def test_a_bolt_hidden_from_the_render_does_not_hide_his_face():
    """round 8: spent bolts stay in the scene (hidden from the render) so FAR/BOLT can measure them, and the face check
    counted them as blocking his face a second after they had gone, which blocked the side lens the notes asked for"""
    src = (STORE / "staging.py").read_text()
    body = src[src.index("def face_hidden"):src.index("def face_dir")]
    assert "hide_render" in body and "blocked >= 3" in body


def test_every_shot_is_graded_against_the_line_spoken_over_it():
    """2026-11-23: the lightning cut passed shot by shot and was held at 61 because the Empire State line played over a
    brown walk-up and Sullivan's seven strikes were one frame; no judge was ever shown the narration"""
    env = dict(os.environ, STORY="lightning")
    code = ("import sys; sys.path.insert(0, %r); import judge3d; print(judge3d.BAR); print('SAYS1=' + judge3d.SAYS[2])"
            % str(STORE))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True).stdout
    assert "NOT SHOWN" in out and "Empire State" in out.split("SAYS1=")[1]
    assert "SAYS (the narration over this shot" in (STORE / "judge3d.py").read_text()
    assert L.tag("NOT SHOWN: a brown walk-up, not the Empire State") == "NOT SHOWN"
