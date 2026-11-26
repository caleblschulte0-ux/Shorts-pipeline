"""Before the judge panel is spent on a storyboard sheet, one cheap look ticks every promise of the texts against a
still of that exact sheet (2026-11-25). The lava short took four board rounds a shot, forty minutes each, and nearly
every round failed on something visible in the sheet before it was sent: a prop the line named and no still showed, a
still graded differently from the rest, a wall cut by the frame edge. Offline: the look is a stand-in here, and the
judge is run on a copy of the store with a stand-in `claude` on PATH."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import preflight3d as PF  # noqa: E402

SCRIPT = {
    "lines": ["hook", "So when the lava came, it hit the wall, and three houses were saved."],
    "storyboard": [
        "1 hook (a street by day; wide): cars leave.",
        "2 the wall holds (the lava side of the earth wall, its black face behind him; low and close at dawn, looking at "
        "the wall): the driver in his hard hat stands braced as a river of lava comes at the wall. It slams into the foot "
        "of the wall beside him and heaps up; he pumps his fists.",
    ],
    "world": {"hero": "Data as the digger driver: a yellow hard hat", "time": "one bright day", "weather": "cold and bright",
              "continuity": {"hard hat": "on his head in every beat", "town house": "the houses he keeps"}},
}


def _all_seen(prompt, miss=(), cont_bad=(), still=2, defect_bad=(), no_defects=False):
    ids = re.findall(r"^- (c\d+) \[", prompt, re.M)
    return json.dumps({"claims": [{"id": i, "seen": i not in miss, "still": still, "note": "the hose is in no still" if i in miss else "there"} for i in ids],
                       "continuity": [{"id": c, "ok": c not in cont_bad, "stills": "2-3", "note": "still 3 is greyer"} for c in PF.CONTINUITY],
                       **({} if no_defects else {"defects": [{"id": d, "ok": d not in defect_bad, "stills": "2-4", "note": "the same run, only bigger"} for d in PF.DEFECTS]})})


@pytest.fixture
def story(tmp_path, monkeypatch):
    monkeypatch.setattr(PF, "STORIES", tmp_path)
    monkeypatch.delenv("PREFLIGHT3D_AGAIN", raising=False)
    import shot_plan    # "s" stands in for a story staged before the plan: this file tests the LOOK; a new story's plan block is held
    monkeypatch.setitem(shot_plan.PLAN_BEFORE, "s", "a stand-in story")     # by tests/test_data3d_a_shot_is_born_to_the_recipe.py
    (tmp_path / "s").mkdir(); (tmp_path / "s" / "script.json").write_text(json.dumps(SCRIPT))
    sheet = tmp_path / "sheet_s2.jpg"; Image.new("RGB", (64, 32), (200, 90, 20)).save(sheet)
    return tmp_path, sheet


def test_the_claims_are_every_promise_of_the_three_texts():
    cl = PF.claims(SCRIPT, 2)
    by = lambda k: [c["text"] for c in cl if c["kind"] == k]
    assert by("PLACE") == ["the lava side of the earth wall", "its black face behind him"]
    assert by("CAMERA") == ["low and close at dawn, looking at the wall"], "the camera words are a promise the render keeps"
    assert "it is dawn" in by("TIME"), "a time of day named in the line"
    assert by("ACTION") == ["the driver in his hard hat stands braced", "a river of lava comes at the wall",
                            "It slams into the foot of the wall beside him and heaps up", "he pumps his fists"]
    assert any("three houses" in t for t in by("NUMBER")), "a number in the spoken line must be seen as a count"
    assert any("it hit the wall" in t for t in by("SAYS"))
    assert by("HERO") and by("WEATHER")
    assert len(by("CONTINUITY")) == 1 and by("CONTINUITY")[0].startswith("the hard hat is in this shot"), "the world's things this line names"
    assert [c["id"] for c in cl] == [f"c{i}" for i in range(1, len(cl) + 1)]
    assert {c["from"] for c in cl} == {"FOR", "SAYS", "WORLD"}
    no_time = PF.claims(dict(SCRIPT, storyboard=["1 x (a street; wide): cars leave."]), 1)
    assert any(c["kind"] == "TIME" and c["from"] == "WORLD" for c in no_time), "with no time in the line, the world's holds"


def test_one_before_a_noun_is_an_article_not_a_count_to_verify():
    """2026-11-25, lava shot 1: "one Icelandic town" became a NUMBER claim and the look blocked the sheet on it"""
    def numbers(line):
        sc = dict(SCRIPT, lines=[line], storyboard=["1 x (a street; wide): cars leave."])
        return [c["text"] for c in PF.claims(sc, 1) if c["kind"] == "NUMBER"]
    assert numbers("A volcano keeps erupting right beside one Icelandic town, and everyone had to run.") == []
    assert numbers("A single wall stood, and a crack ran through one street.") == []
    assert len(numbers("Three houses burned.")) == 1
    assert len(numbers("Europe's tests caught one honey import in seven faked.")) == 2, "one against a count is a count"
    import story_gate
    assert story_gate.line_showable_problems("A volcano keeps erupting right beside one Icelandic town.") == []


def test_the_spoken_line_is_checked_by_the_judges_own_standard_and_no_looser():
    """same sheet: a fire curtain over a street and the hero sprinting away was blocked for "does not show Iceland or
    everyone running". The panel asks whether a stranger could tell the fact from the picture; so does the look."""
    says = [c["text"] for c in PF.claims(SCRIPT, 2) if c["kind"] == "SAYS"]
    assert len(says) == 1 and says[0].startswith("a stranger with the sound off would say the stills show what this line says")
    brief = " ".join(PF.PROMPT.split())
    for must in ("could a stranger tell the line's fact from these stills", "shown by the place itself", "never by a label",
                 "is shown when the hero is seen doing it", "Do NOT tick it when an event or a thing the line names is depicted in no still",
                 "only a generic stand-in", "only the voice could state", "no stricter and no looser"):
        assert must in brief, must
    judge = " ".join((D3 / "store" / "judge3d.py").read_text().split())
    assert "With the sound off a stranger must be able to tell the fact from the picture" in judge, "the standard is the judge's, read not restated"
    cl = PF.claims(SCRIPT, 2); sid = next(c["id"] for c in cl if c["kind"] == "SAYS")
    un, _ = PF.decide(cl, json.loads(_all_seen(PF.prompt(cl, "x.jpg", 4), miss={sid})), 4)
    assert [c["kind"] for c in un] == ["SAYS"], "a line whose event no still depicts still blocks"


def test_every_claim_ticked_against_a_still_is_a_recorded_pass_for_that_sheet(story):
    tmp, sheet = story
    asked = []
    rec = PF.check("s", 2, sheet, 4, look=lambda p: asked.append(p) or _all_seen(p))
    assert rec["status"] == "pass" and PF.passed("s", 2, sheet)
    assert str(sheet) in asked[0] and "c1 [PLACE, from FOR]" in asked[0] and "props:" in asked[0]
    led = json.loads((tmp / "s" / PF.NAME).read_text())
    assert list(led["sheets"]) == [PF.sheet_sha(sheet)], "the result is keyed by the sheet's sha256"
    again = PF.check("s", 2, sheet, 4, look=lambda p: pytest.fail("a sheet already passed is not looked at twice"))
    assert again["kept"] and again["status"] == "pass"


def test_one_unticked_claim_blocks_and_says_what_to_fix_or_which_promise_to_remove(story, capsys):
    tmp, sheet = story
    res = PF.gate("s", [(2, sheet, 4)], look=lambda p: _all_seen(p, miss={"c6"}))
    assert res[2]["status"] == "blocked" and not PF.passed("s", 2, sheet)
    out = capsys.readouterr().out
    assert "BLOCKED before the panel" in out and "a river of lava comes at the wall" in out
    assert "Fix the shot so one still shows it, or take that promise out of the shot's storyboard line" in out
    v = PF.verdict(res[2])
    assert v["pass"] is False and v["score"] == 0 and v["preflight"] and v["hard"][0].startswith("PRE-FLIGHT: NOT SEEN [ACTION")


def test_a_claim_is_only_ticked_against_a_specific_still(story):
    tmp, sheet = story
    cl = PF.claims(SCRIPT, 2)
    for bad_still in (None, 0, 5, "2", True):
        un, _ = PF.decide(cl, json.loads(_all_seen(PF.prompt(cl, sheet, 4), still=bad_still)), 4)
        assert len(un) == len(cl), f"still={bad_still!r} names no still of the four"
    un, faults = PF.decide(cl, {"claims": [], "continuity": []}, 4)
    assert len(un) == len(cl) and len(faults) == len(PF.CONTINUITY), "what the look left out is not ticked"


def test_a_continuity_fault_between_stills_blocks(story):
    tmp, sheet = story
    for cid in PF.CONTINUITY:
        rec = PF.check("s", 2, sheet, 4, look=lambda p: _all_seen(p, cont_bad={cid}))
        assert rec["status"] == "blocked" and rec["continuity"][0]["id"] == cid
        (tmp / "s" / PF.NAME).unlink()
    assert set(PF.CONTINUITY) == {"props", "grade", "feet", "edges", "different"}


def test_a_hard_defect_the_judges_would_fail_blocks_like_an_unticked_claim(story, capsys):
    """2026-11-26: a sheet with every claim ticked went to the panel and failed on four stills of one run and two stray
    rods. The look now answers the judges' hard-defect classes too, and code blocks on any one of them."""
    tmp, sheet = story
    assert set(PF.DEFECTS) == {"gag", "broken", "look", "body", "consequence"}
    for did in PF.DEFECTS:
        rec = PF.check("s", 2, sheet, 4, look=lambda p: _all_seen(p, defect_bad={did}))
        assert rec["status"] == "blocked" and [d["id"] for d in rec["defects"]] == [did] and not rec["unticked"] and not rec["continuity"]
        assert not PF.passed("s", 2, sheet)
        assert any(l.startswith(f"HARD DEFECT {did} (stills 2-4): the same run, only bigger") for l in PF.lines(rec))
        (tmp / "s" / PF.NAME).unlink()
    rec = PF.check("s", 2, sheet, 4, look=lambda p: _all_seen(p, no_defects=True))
    assert rec["status"] == "blocked" and len(rec["defects"]) == len(PF.DEFECTS), "a question the look left out is not answered ok"
    (tmp / "s" / PF.NAME).unlink()
    cl = PF.claims(SCRIPT, 2); text = PF.prompt(cl, str(sheet), 4)
    for what in PF.DEFECTS.values():
        assert what in text, "every question is put to the look"
    PF.gate("s", [(2, str(sheet), 4)], look=lambda p: _all_seen(p, defect_bad={"gag"}))
    assert "1 hard defect(s)" in capsys.readouterr().out
    assert PF.verdict(PF.check("s", 2, sheet, 4, look=_all_seen))["pass"] is False


def test_a_pass_from_before_the_questions_were_asked_is_no_pass(story, monkeypatch):
    tmp, sheet = story
    assert PF.check("s", 2, sheet, 4, look=_all_seen)["status"] == "pass" and PF.passed("s", 2, sheet)
    monkeypatch.setitem(PF.DEFECTS, "new", "a question nobody asked of that sheet")
    assert not PF.passed("s", 2, sheet)


def test_no_answer_is_no_pass_and_nothing_is_recorded(story):
    tmp, sheet = story
    for answer in (None, "", "I could not open the file", '{"claims": "all fine"}'):
        rec = PF.check("s", 2, sheet, 4, look=lambda p: answer)
        assert rec["status"] == "no_look" and not PF.passed("s", 2, sheet)
    assert not (tmp / "s" / PF.NAME).exists()


def test_a_pass_is_for_that_exact_sheet_and_those_exact_texts(story):
    tmp, sheet = story
    PF.check("s", 2, sheet, 4, look=_all_seen)
    assert PF.passed("s", 2, sheet)
    other = tmp / "other.jpg"; Image.new("RGB", (64, 32), (10, 10, 10)).save(other)
    assert not PF.passed("s", 2, other), "another sheet has no pre-flight"
    assert not PF.passed("s", 1, sheet), "another shot has no pre-flight"
    changed = json.loads(json.dumps(SCRIPT)); changed["storyboard"][1] = changed["storyboard"][1].replace("pumps his fists", "waves a hose")
    (tmp / "s" / "script.json").write_text(json.dumps(changed))
    assert not PF.passed("s", 2, sheet), "a new promise in the text needs a new look"


def test_a_blocked_sheet_stays_blocked_until_the_shot_or_the_text_changes(story, monkeypatch):
    tmp, sheet = story
    PF.check("s", 2, sheet, 4, look=lambda p: _all_seen(p, miss={"c5"}))
    rec = PF.check("s", 2, sheet, 4, look=lambda p: pytest.fail("the same sheet is not looked at again by default"))
    assert rec["status"] == "blocked" and rec["kept"]
    monkeypatch.setenv("PREFLIGHT3D_AGAIN", "1")
    assert PF.check("s", 2, sheet, 4, look=_all_seen)["status"] == "pass", "a second look is a look, never a skip"


def test_it_can_only_add_a_block():
    """the pre-flight has no say in a score and cannot pass a shot: the judge's bar and prompt are where they were"""
    pf = (D3 / "store" / "preflight3d.py").read_text()
    assert "PASS_SCORE" not in pf and "import judge3d" not in pf
    assert '"pass": False' in pf[pf.index("def verdict("):pf.index("def main(")]
    j = (D3 / "store" / "judge3d.py").read_text()
    assert re.search(r"^PASS_SCORE = 70$", j, re.M)
    assert 's["pass"] = not s.get("hard") and (s.get("score") or 0) >= PASS_SCORE' in j
    assert "pass: true only when there is NO hard defect AND score >= 70" in j
    main = j[j.index("def main():"):]
    assert main.index("preflight3d.gate(story, sheets)") < main.index("subprocess.Popen(cmd"), "the look comes before the panel"
    assert "if preflight3d.passed(story, n_, p_)]" in main, "only a sheet with a recorded pass reaches the panel"
    assert "claude" in pf and "anthropic" not in pf.lower().replace("never the paid api", ""), "the headless CLI, never the paid API"


# ---------------------------------------------------------------- the judge itself, on a copy of the store
FAKE = '''#!{py}
import json, os, re, sys
prompt = sys.argv[sys.argv.index("-p") + 1]
log = open(os.environ["FAKE_LOG"], "a")
if "checking a storyboard sheet before it is sent" in prompt:
    log.write("preflight\\n")
    if os.environ.get("FAKE_SILENT"): sys.exit(1)
    ids = re.findall(r"^- (c\\d+) \\[", prompt, re.M)
    miss = os.environ.get("FAKE_MISS", "").split()
    print(json.dumps({{"claims": [{{"id": i, "seen": i not in miss, "still": 1, "note": "not in any still"}} for i in ids],
                      "continuity": [{{"id": c, "ok": True}} for c in ("props", "grade", "feet", "edges", "different")],
                      "defects": [{{"id": d, "ok": True}} for d in ("gag", "broken", "look", "body", "consequence")]}}))
else:
    log.write("panel\\n")
    shots = [int(n) for n in re.findall(r"^- shot (\\d+):", prompt, re.M)]
    print(json.dumps({{"shots": [{{"shot": n, "score": 80, "pass": True, "hard": [], "problems": [], "better": []}} for n in shots]}}))
'''


def _judge(tmp_path, board=True, **env):
    store = tmp_path / "tools" / "data3d" / "store"
    if not store.exists():
        store.mkdir(parents=True)
        for name in ("judge3d", "look_bible", "notes_ledger", "rounds", "judged", "preflight3d", "story_gate", "boardlint"):
            shutil.copy(D3 / "store" / f"{name}.py", store)
        shutil.copy(D3 / "clock.py", store.parent)
        # the pre-flight asks the plan first (store/shot_plan.py); "s" stands in for a story staged before the plan
        (store / "shot_plan.py").write_text((D3 / "store" / "shot_plan.py").read_text() + '\nPLAN_BEFORE["s"] = "a stand-in story in a test"\n')
        (store.parent / "stories" / "s").mkdir(parents=True)
        (store.parent / "stories" / "s" / "script.json").write_text(json.dumps(SCRIPT))
        (tmp_path / "scripts").symlink_to(ROOT / "scripts")
        (tmp_path / "bin").mkdir()
        fake = tmp_path / "bin" / "claude"; fake.write_text(FAKE.format(py=sys.executable)); fake.chmod(0o755)
        for n in (1, 2):
            d = tmp_path / "board" / f"s{n}"; d.mkdir(parents=True)
            for f in range(1, 5):
                Image.new("RGB", (54, 96), (40 * f, 30 * n, 20)).save(d / f"f{f:04d}.png")
    log = tmp_path / "log.txt"; log.write_text("")
    e = {k: v for k, v in os.environ.items() if not k.startswith(("JUDGE3D", "PREFLIGHT3D", "FAKE_", "SHOTS"))}
    e.update(STORY="s", PATH=f"{tmp_path / 'bin'}:/usr/bin:/bin", FAKE_LOG=str(log), JUDGE3D_REJUDGE="1", **env)
    if board:
        e["JUDGE3D_BOARD"] = "1"
    r = subprocess.run([sys.executable, str(store / "judge3d.py"), str(tmp_path / "board"), str(tmp_path / "board" / "v.json")],
                       env=e, capture_output=True, text=True, cwd=str(store))
    v = tmp_path / "board" / "v.json"
    verdict = json.loads(v.read_text()) if v.exists() else None
    if v.exists(): v.unlink()
    return r, log.read_text().split(), verdict


def test_a_board_round_with_an_unticked_claim_never_reaches_the_panel(tmp_path):
    r, calls, v = _judge(tmp_path, FAKE_MISS="c1")
    assert r.returncode == 2, r.stdout + r.stderr
    assert calls.count("preflight") == 2 and "panel" not in calls, "no judge run is spent on a sheet with a visible fault"
    assert all(s["pass"] is False and s["preflight"] and s["hard"][0].startswith("PRE-FLIGHT") for s in v["shots"])
    assert "BLOCKED before the panel" in r.stdout
    rounds = (tmp_path / "tools" / "data3d" / "stories" / "s" / "judge_rounds.md").read_text()
    assert "PRE-FLIGHT: NOT SEEN" in rounds, "the round report says why no panel sat"
    assert not (tmp_path / "tools" / "data3d" / "stories" / "s" / "notes_ledger.json").exists(), "the ledger keeps the panel's notes only"


def test_a_board_round_with_every_claim_ticked_goes_to_the_panel_and_the_panel_decides(tmp_path):
    r, calls, v = _judge(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert calls.count("preflight") == 2 and calls.count("panel") == 3, "one look per sheet, then the same panel of three"
    assert [(s["shot"], s["score"], s["pass"]) for s in v["shots"]] == [(1, 80, True), (2, 80, True)]
    assert not any(s.get("preflight") for s in v["shots"])
    r, calls, v = _judge(tmp_path)
    assert "preflight" not in calls and calls.count("panel") == 3, "the same sheet is not looked at twice; the panel still sits"


def test_a_board_round_with_no_look_does_not_run(tmp_path):
    r, calls, v = _judge(tmp_path, FAKE_SILENT="1")
    assert r.returncode == 1 and v is None and "panel" not in calls, r.stdout + r.stderr
    assert "no pre-flight, no panel" in r.stdout


def test_a_proof_round_is_judged_as_before(tmp_path):
    r, calls, v = _judge(tmp_path, board=False)
    assert r.returncode == 0 and "preflight" not in calls and calls.count("panel") == 3, r.stdout + r.stderr
