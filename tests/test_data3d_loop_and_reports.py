"""THE 180 RULE and THE ROUND REPORT (2026-11-14), held offline.

  - 180: after FLIP (3) rounds under the judge's bar on ONE idea, the proof loop stops polishing and demands a
    DIFFERENT IDEA for the narration line, every camera / timing / framing tweak of the old idea forbidden, and the new
    idea is judged on its own (never undone back to the old one). It is recorded in loop.json and judge_rounds.md.
    (caaleb, of saffron shot 4: "90 degrees didn't work 3 times, try 180".)
  - ROUND REPORT: every judge3d run appends a per-shot summary (score, panel, pass/fail, the judge's named problems) to
    stories/<story>/judge_rounds.md, and CI carries a copy beside the verdict."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
import proof_loop as pl  # noqa: E402
import rounds  # noqa: E402


def _main_src():
    return ast.unparse(next(n for n in ast.walk(ast.parse(Path(pl.__file__).read_text())) if isinstance(n, ast.FunctionDef) and n.name == "main"))


def test_the_bar_is_the_judges_own():
    assert pl.PASS == int(re.search(r"^PASS_SCORE = (\d+)", (STORE / "judge3d.py").read_text(), re.M).group(1))
    assert pl.FLIP == 3


def test_three_rounds_under_the_bar_is_a_180():
    assert not pl.needs_new_idea([50, 60])
    assert pl.needs_new_idea([50, 60, 66])
    assert not pl.needs_new_idea([50, 72, 66]), "a round at the bar breaks the run"
    assert not pl.needs_new_idea([50, 60, 66, 40], since=3), "a new idea gets its own three rounds"
    assert pl.needs_new_idea([50, 60, 66, 40, 41, 52], since=3)


def test_the_180_prompt_demands_a_new_idea_and_forbids_tweaking_the_old_one():
    kind, text = pl.rethink_kind([55, 61, 64], [["the dial is tiny"]] * 3, 0, "It's a race against the sun.",
                                 "a ringing alarm clock while the flower wilts", ["a pile of cash for one tiny jar"])
    assert kind == "180"
    assert "It's a race against the sun." in text and "DIFFERENT IDEA" in text
    assert "a ringing alarm clock while the flower wilts" in text and "a pile of cash for one tiny jar" in text
    for banned in ("camera", "re-timing", "reframing", "lens", "bigger"):
        assert banned in text, banned
    assert "NEW IDEA:" in text


def test_the_180_comes_before_a_stall_and_a_stall_is_still_a_rethink():
    assert pl.rethink_kind([62, 58, 61], [[], [], []], 0, "l", "i", [])[0] == "180"
    k, t = pl.rethink_kind([72, 60, 64, 70, 71], [["stain"]] * 5, 3, "l", "i", [])     # since=3: two rounds of a new idea
    assert k == "" and t == ""
    assert pl.rethink_kind([40, 66, 75, 74, 73], [["the stain"], ["a stain"], ["stain"], ["stain"], ["stain"]], 0, "l", "i", [])[0] == "stall"


def test_the_loop_records_the_decision_and_never_undoes_a_new_idea():
    body = _main_src()
    assert "rethink_kind(" in body and "rounds.note(" in body and "decision_note(" in body
    assert "'rethink'" in body or '"rethink"' in body, "loop.json carries the decision"
    assert "fresh.add(n)" in body and "n in fresh" in body, "a new idea is judged on its own, not undone to the old one"
    assert "since[n] = len(scores[n])" in body
    note = pl.decision_note(4, 2, "180", [55, 61, 64], "NEW IDEA: a dam bursts")
    assert "180" in note and "DIFFERENT IDEA" in note and "NEW IDEA: a dam bursts" in note


def test_the_round_report_names_every_shot_and_its_problems(tmp_path, monkeypatch):
    monkeypatch.setattr(rounds, "STORIES", tmp_path)
    (tmp_path / "demo").mkdir()
    shots = [{"shot": 1, "score": 81, "scores": [78, 81, 84], "pass": True, "hard": [], "problems": ["a little dark"]},
             {"shot": 2, "score": 58, "scores": [55, 58, 62], "pass": False, "hard": ["the needle never moves, frames 3-9"],
              "problems": ["the dial is a few pixels on a phone"], "better": ["make the needle a metre long"]},
             {"shot": 3, "score": 75, "pass": True, "kept": "passed earlier"}]
    copy = tmp_path / "copy.md"
    p = rounds.append("demo", shots, mode="proof", round_no=2, copy_to=copy, pass_score=70)
    rounds.note("demo", "round 2, shot 2: THE 180 RULE")
    rounds.append("demo", shots[:1], mode="storyboard", round_no=3)
    txt = p.read_text()
    assert txt.startswith("# Judge rounds: demo")
    assert txt.count("## ") == 2 and "· proof · round 2" in txt and "· storyboard · round 3" in txt
    assert "| 2 | 58 | 55, 58, 62 | FAIL |" in txt and "| 3 | 75 | - | PASS (kept) |" in txt
    assert "HARD: the needle never moves" in txt and "problem: the dial is a few pixels on a phone" in txt
    assert "> round 2, shot 2: THE 180 RULE" in txt
    assert copy.read_text().count("## ") == 1, "the copy is the file as of that run"
    assert rounds.append("nosuchstory", shots) is None, "never invents a story folder"


def test_every_judge_run_writes_the_report_and_ci_keeps_it():
    src = (STORE / "judge3d.py").read_text()
    main = ast.unparse(next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "main"))
    assert main.count("report(") >= 3, "kept passes, a judged panel and a panel that did not answer are all reported"
    assert "rounds.append(" in src
    wf = (ROOT / ".github" / "workflows" / "data3d_render.yml").read_text()
    assert "proof/judge_rounds.md" in wf and "art/verdict/judge_rounds.md" in wf
    loop = Path(pl.__file__).read_text()
    assert "JUDGE3D_ROUND=" in loop, "the loop tells the judge which round it is"
    assert re.search(r"CHECKS = re\.compile\(.*HANDS", loop) and re.search(r"CHECKS = re\.compile\(.*BOARD", loop)
