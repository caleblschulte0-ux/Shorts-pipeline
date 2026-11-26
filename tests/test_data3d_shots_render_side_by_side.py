"""THE SHOTS OF A 3D SHORT RUN SIDE BY SIDE, BEHIND THE SAME GATE (2026-11-26).

A 3D short is five shots that do not depend on each other. A board round judged them one after another in a session
(about 25 minutes each), and a fix to one shot rendered all five again. Now:

  * data3d_board.yml judges every shot's storyboard stills on its own runner and writes the round where a session's
    round writes it. It is a judge run: it makes no video, opens no gate and posts nothing.
  * data3d_render.yml plans the frames per shot AFTER the gate (store/render_plan.py) and copies a shot whose key is
    unchanged from the run that rendered it.

What must never move is held here: no frame renders before the proof and the judge have passed (or caaleb's own words
let a failed panel through, which only the judge job reads); the assembly needs every frame; a key changes with
anything a shot's pixels are made from; and the board workflow cannot start, pass or replace any of that."""
import json
import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
STORE = ROOT / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
import board_ci
import render_plan as rp


def _wf(name):
    src = (WF / name).read_text()
    doc = yaml.safe_load(src)
    return src, doc, doc["jobs"]


def _runs(job):
    return "\n".join(s.get("run", "") for s in job["steps"])


def _needs(job):
    n = job.get("needs", [])
    return [n] if isinstance(n, str) else list(n)


# ------------------------------------------------------------------------------------------------ the render's gate
GATE = "needs.proof.result == 'success' && needs.judge.result == 'success'"


def test_no_frame_and_no_plan_starts_before_the_proof_and_the_judge_have_passed():
    _, _, jobs = _wf("data3d_render.yml")
    for name in ("plan", "frames"):
        j = jobs[name]
        assert {"proof", "judge"} <= set(_needs(j)), f"{name} must wait for the proof and the judge"
        assert j["if"].startswith("always() && " + GATE), f"{name} carries the gate's own condition, word for word"
        assert "continue-on-error" not in j
    assert "plan" in _needs(jobs["frames"]) and "needs.plan.result == 'success'" in jobs["frames"]["if"]
    # every job that runs Blender on the full video sits behind the gate: only the proof may render before it
    for name, j in jobs.items():
        if "render_range.py" in _runs(j):
            assert name == "frames"
    assert "shots.py" in _runs(jobs["proof"]) and "render_range.py" not in _runs(jobs["proof"])


def test_the_gate_itself_is_as_it_was():
    src, doc, jobs = _wf("data3d_render.yml")
    judge = _runs(jobs["judge"])
    assert '[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ] || { echo "::error::CLAUDE_CODE_OAUTH_TOKEN is not set: no judge, no render"; exit 1; }' in judge
    # the one way past a panel that failed is the operator's own words, read from the trigger by cfg and by no one else
    assert re.search(r'judge3d\.py proof proof/verdict\.json \\?\s*\n?\s*\|\| \{ \[ -n "\$OPERATOR_SAID" \] && echo', judge)
    assert src.count("OPERATOR_SAID") == 3 and src.count("operator_said") >= 3
    for name, j in jobs.items():
        if name not in ("cfg", "judge"):
            assert "operator_said" not in json.dumps(j).lower(), f"{name} must not read the operator's words"
    assert jobs["judge"]["if"] == "always() && needs.proof.result == 'success'"
    assert _needs(jobs["proof"]) == ["cfg", "narrate"]
    proof = _runs(jobs["proof"])
    assert "set -o pipefail" in proof and proof.index("set -o pipefail") < proof.index("| grep")
    assert doc["concurrency"] == {"group": "data3d-render", "cancel-in-progress": True}
    on = doc[True]["push"]
    assert on["paths"] == [".github/triggers/data3d_render"] and "schedule" not in doc[True]


def test_the_assembly_needs_every_shot_and_every_frame():
    _, _, jobs = _wf("data3d_render.yml")
    a = jobs["assemble"]
    assert "frames" in _needs(a) and a["if"] == "always() && needs.frames.result == 'success'", \
        "a matrix is 'success' only when every one of its jobs is: one failed shot part and nothing is assembled"
    assert jobs["frames"]["strategy"]["matrix"] == {"include": "${{ fromJSON(needs.plan.outputs.matrix) }}"}
    run = _runs(a)
    assert "clock.total(" in run and run.index("clock.total(") < run.index("story/assemble.py"), \
        "assemble.py globs the frames: a missing one must stop the assembly, not shorten the video"
    fr = jobs["frames"]["steps"]
    names = [s.get("name", s.get("uses", "")) for s in fr]
    check = next(i for i, n in enumerate(names) if n.startswith("Every frame of the range is here"))
    upload = next(i for i, s in enumerate(fr) if "upload-artifact" in s.get("uses", ""))
    assert check < upload and "if" not in fr[check], "a part is counted before it becomes an artifact, copied or rendered"
    assert fr[upload]["with"]["name"] == "${{ matrix.artifact }}"


def test_the_same_frames_at_the_same_settings():
    _, _, jobs = _wf("data3d_render.yml")
    plan = jobs["plan"]["steps"][-1]
    assert "bpy==5.0.0" in plan["env"]["RENDER_ENV"] and "LOOK=NYC" in plan["env"]["RENDER_ENV"]
    render = next(s for s in jobs["frames"]["steps"] if s.get("name", "").startswith("Render this part"))
    assert render["env"]["LOOK"] == "NYC"
    deps = next(s for s in jobs["frames"]["steps"] if s.get("name") == "Deps")
    for pin in plan["env"]["RENDER_ENV"].split()[1:]:
        assert pin in deps["run"], f"the key says {pin}; the frames job must install exactly that"
    assert 'render_range.py ${{ matrix.a }} ${{ matrix.b }}' in render["run"]
    assert '"${{ matrix.spp }}" "${{ matrix.pct }}"' in render["run"]


# ------------------------------------------------------------------------------------------------------- the plan
W = [[0.0, 4.378], [4.378, 7.649], [7.649, 10.788], [10.788, 14.775], [14.775, 19.883]]
KEYS = {n: f"{n:016x}" for n in range(1, 6)}


def _frames(m):
    return sorted(f for x in m for f in range(x["a"], x["b"] + 1))


def test_a_plan_tiles_the_video_and_no_job_crosses_a_cut():
    total = rp.clock.total(W)
    for parts in (5, 40, 80, 400):
        for reuse in ({}, {2: (111, KEYS[2])}, {n: (111, rp.MANUAL) for n in (1, 2, 4, 5)}):
            m = rp.plan(W, KEYS, parts, reuse)
            assert _frames(m) == list(range(1, total + 1)), "every frame once: no gap, no overlap"
            for x in m:
                _, _, g0, nf = rp.clock.span(W, x["shot"])
                assert g0 < x["a"] <= x["b"] <= g0 + nf and x["frames"] == x["b"] - x["a"] + 1
                assert x["reuse_run"] or x["frames"] >= rp.MIN_FRAMES or x["parts"] == 1
            assert len({x["artifact"] for x in m}) == len(m)
            assert len(m) <= max(parts, len(W))
            copied = [x for x in m if x["reuse_run"]]
            assert sorted(x["shot"] for x in copied) == sorted(reuse) and m[len(m) - len(copied):] == copied


def test_a_shot_is_copied_only_from_a_run_that_holds_all_of_it_under_its_key():
    k = KEYS[3]
    whole = [rp.artifact(3, k, i, 4) for i in range(4)]
    assert rp.holds(whole + ["narration", "proof-3"], 3, k)
    assert not rp.holds(whole[:3], 3, k), "three parts of four is not the shot"
    assert not rp.holds(whole, 2, k) and not rp.holds(whole, 3, KEYS[2])
    assert not rp.holds([rp.artifact(3, k, 0, 2), rp.artifact(3, k, 1, 3), rp.artifact(3, k, 2, 3)], 3, k)
    # frames taken on a session's word carry no key, so no later run finds them by one
    m = rp.plan(W, KEYS, 80, {3: (111, rp.MANUAL)})
    took = next(x for x in m if x["shot"] == 3)
    assert took["artifact"] == "frames-s3-manual-p0of1" and took["pattern"] == "frames-s3-*"
    assert not re.fullmatch(r"[0-9a-f]+", rp.MANUAL)
    assert not rp.holds([took["artifact"]], 3, k)
    auto = next(x for x in rp.plan(W, KEYS, 80, {3: (111, k)}) if x["shot"] == 3)
    assert auto["pattern"] == f"frames-s3-{k}-p*" and rp.holds([auto["artifact"]], 3, k), "a copy can be copied again"


@pytest.fixture
def story(tmp_path, monkeypatch):
    d3 = tmp_path / "data3d"; store = d3 / "store"; sd = d3 / "stories" / "s"
    store.mkdir(parents=True); sd.mkdir(parents=True); (d3 / "stories" / "other").mkdir()
    (store / "shots.py").write_text("import scene_kit as K, clock\nimport subprocess\nsubprocess.run(['python3', 'labels.py'])\n")
    (store / "scene_kit.py").write_text("import style\nU = 1\n")
    (store / "style.py").write_text("X = 1\n")
    (store / "labels.py").write_text("L = 1\n")
    (store / "judge3d.py").write_text("PASS_SCORE = 70\n")
    (d3 / "clock.py").write_text("FPS = 30\n")
    (d3 / "stories" / "other" / "shots.py").write_text("def shot1():\n    pass\n")
    (sd / "script.json").write_text('{"lines": ["a", "b"]}')
    (sd / "shots.py").write_text("import locations\n\ndef helper():\n    return 1\n\n\ndef shot1():\n    return helper()\n\n\n"
                                 "def shot2():\n    return 2\n\n\nSHOTS = {1: shot1, 2: shot2}\n")
    (store / "locations.py").write_text("P = 1\n")
    monkeypatch.setattr(rp, "HERE", store); monkeypatch.setattr(rp, "D3", d3); monkeypatch.setattr(rp, "STORIES", d3 / "stories")
    key = lambda n, **kw: rp.shot_key("s", n, kw.pop("w", W[:2]), kw.pop("spp", 16), kw.pop("pct", 100), **kw)
    return d3, key


def test_a_key_changes_with_anything_the_pixels_are_made_from(story):
    d3, key = story
    base = {n: key(n) for n in (1, 2)}
    def changed(path, text, append=True):
        p = d3 / path; old = p.read_text() if p.exists() else None
        p.write_text((old or "") + text if append else text)
        now = {n: key(n) for n in (1, 2)}
        p.write_text(old) if old is not None else p.unlink()
        assert {n: key(n) for n in (1, 2)} == base, "the key is a function of the files, nothing else"
        return {n for n in now if now[n] != base[n]}
    assert changed("store/shots.py", "# x\n") == {1, 2}, "the harness"
    assert changed("store/style.py", "# x\n") == {1, 2}, "a module imported by a module the harness imports"
    assert changed("store/locations.py", "# x\n") == {1, 2}, "a module only the STORY imports"
    assert changed("store/labels.py", "# x\n") == {1, 2}, "a file run by its name, never imported"
    assert changed("clock.py", "# x\n") == {1, 2}
    assert changed("stories/s/script.json", " ") == {1, 2}
    assert changed("stories/s/texture.dat", "x") == {1, 2}, "a data file beside the story"
    src = (d3 / "stories/s/shots.py").read_text()
    assert changed("stories/s/shots.py", src.replace("return 1", "return 3"), append=False) == {1, 2}, "a helper is everyone's"
    assert changed("stories/s/shots.py", src.replace("return 2", "return 22"), append=False) == {2}, "shot 2's own function is shot 2's"
    assert changed("stories/s/shots.py", src.replace("return helper()", "return helper() + 1"), append=False) == {1}
    # what is not pixels: the judge's records, another story, a module nothing on the render path names
    for rec in rp.RECORDS:
        assert changed(f"stories/s/{rec}", "x") == set(), rec
    assert changed("stories/other/shots.py", "# x\n") == set()
    assert changed("store/judge3d.py", "# x\n") == set()
    # the settings and the voice
    assert key(1, spp=24) != base[1] and key(1, pct=60) != base[1]
    assert key(1, assets="abc") != base[1] and key(1, env="bpy==5.1") != base[1]
    assert key(1, w=[[0.0, 4.4], [4.4, 7.649]]) != base[1]
    assert set(rp.RECORDS) >= set(board_ci.RECORDS), "what a board round commits never re-renders a shot"


def test_a_shot_another_shot_calls_is_never_blanked(story):
    d3, key = story
    p = d3 / "stories/s/shots.py"
    p.write_text(p.read_text().replace("return helper()", "return helper() + shot2()"))
    one = key(1)
    p.write_text(p.read_text().replace("return 2", "return 22"))
    assert key(1) != one, "shot 1 calls shot 2: shot 2's body is part of shot 1's pixels"


def test_a_computed_import_makes_the_whole_tree_the_key(story):
    d3, key = story
    (d3 / "store" / "scene_kit.py").write_text("import importlib\nm = importlib.import_module('sty' + 'le')\n")
    (d3 / "store" / "stray.py").write_text("S = 1\n")
    one = key(1)
    (d3 / "store" / "stray.py").write_text("S = 2\n")
    assert key(1) != one, "when the imports cannot be followed, every file counts"


def test_every_story_has_a_key_for_every_shot():
    for sd in sorted(p for p in rp.STORIES.iterdir() if (p / "shots.py").exists() and (p / "script.json").exists()):
        w = json.loads((sd / "script.json").read_text()).get("draft_windows")
        if not w:
            continue
        mods = {p.name for p in rp.render_modules((sd / "shots.py").read_text())}
        assert {"shots.py", "scene_kit.py", "character.py", "clock.py", "base_build.py"} <= mods, sd.name
        keys = [rp.shot_key(sd.name, n, w, 16, 100) for n in range(1, len(w) + 1)]
        assert len(set(keys)) == len(keys) and all(re.fullmatch(r"[0-9a-f]{16}", k) for k in keys), sd.name


# ---------------------------------------------------------------------------------------------- the board workflow
def test_the_board_round_only_judges_and_never_publishes_or_renders_a_video():
    src, doc, jobs = _wf("data3d_board.yml")
    on = doc[True]
    assert set(on) == {"push"} and on["push"]["paths"] == [".github/triggers/data3d_board"], \
        "started by its own trigger file and by nothing else: no cron (the clock has nothing to register), no dispatch"
    low = src.lower()
    for word in ("preview-renders", "youtube", "tiktok", "uploader", "videos.insert", "upload_video", "assemble.py",
                 "render_range.py", "ffmpeg", "yt_", "post_stories", "operator_said", "best_cut"):
        assert word not in low, f"a board round has no business with {word!r}"
    code = "\n".join(_runs(j) for j in jobs.values())
    assert "triggers/data3d_render" not in code and "data3d_assemble" not in code and "data3d_narrate" not in code, \
        "it never starts a render, an assembly or a voice"
    assert "judged.py" not in code and "judged.json" not in code and "judged.record" not in code, \
        "a storyboard pass is never recorded as a pass the render's gate would keep"
    secrets = set(re.findall(r"secrets\.(\w+)", src))
    assert secrets == {"CLAUDE_CODE_OAUTH_TOKEN"}, "the judge's token and no channel's"
    assert doc["permissions"] == {"contents": "write", "actions": "read"}
    for path in re.findall(r"git add ([^\n;]+)", code):
        assert path.strip() == '"$d/$f"', path
    assert re.search(r"for f in judge_rounds\.md notes_ledger\.json preflight\.json; do", code)
    assert tuple(board_ci.RECORDS) == ("judge_rounds.md", "notes_ledger.json", "preflight.json")
    assert "push -f" not in code and "--force" not in code
    assert 'git push -q origin HEAD:"$BRANCH"' in code and "FETCH_HEAD" in code, "written on the branch's tip, pushed, retried"


def test_the_board_round_is_the_sessions_round_with_the_same_judge():
    _, _, jobs = _wf("data3d_board.yml")
    sh = (STORE / "board3d.sh").read_text()
    shot = jobs["shot"]
    stills = next(s for s in shot["steps"] if s.get("id") == "stills")
    judge = next(s for s in shot["steps"] if s.get("id") == "judge")
    # board3d.sh: SHOT=$n KEYS=$KEYS STAGING=strict $PY -I shots.py "$OUT/s$n" 8 30
    assert 'STAGING=strict $PY -I shots.py "$OUT/s$n" 8 30' in sh
    assert stills["env"]["STAGING"] == "strict" and "KEYS" in stills["env"]
    assert 'python -I shots.py "$B/s$SHOT" 8 30' in stills["run"]
    # board3d.sh: JUDGE3D_BOARD=1 JUDGE3D_REJUDGE=1 python3 judge3d.py "$OUT" "$OUT/board_verdict.json"
    assert "JUDGE3D_BOARD=1 JUDGE3D_REJUDGE=1 python3 judge3d.py" in sh
    assert judge["env"]["JUDGE3D_BOARD"] == "1" and judge["env"]["JUDGE3D_REJUDGE"] == "1"
    assert judge["env"]["SHOTS"] == "${{ matrix.shot }}"
    assert 'python tools/data3d/store/judge3d.py "$B" "$B/verdict.json"' in judge["run"]
    for k in judge["env"]:
        assert k in ("CLAUDE_CODE_OAUTH_TOKEN", "SHOTS", "JUDGE3D_BOARD", "JUDGE3D_REJUDGE", "JUDGE3D_LABEL"), \
            f"{k}: the panel's size, model, bar and timeout are judge3d.py's own, never set here"
    assert judge["if"] == "steps.stills.outputs.ok == '1'"
    assert '[ "$code" = 0 ] || [ "$code" = 2 ]' in judge["run"], "no judge (exit 1) is a red job, never a result"
    # the preflight: no token, no round, before any runner renders a still
    cfg = _runs(jobs["cfg"])
    assert '[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ] || { echo "::error::CLAUDE_CODE_OAUTH_TOKEN is not set: no judge, no board round"; exit 1; }' in cfg
    assert _needs(shot) == ["cfg"] and shot["strategy"]["matrix"]["shot"] == "${{ fromJSON(needs.cfg.outputs.shots) }}"
    assert shot["strategy"]["fail-fast"] is False


def _art(tmp_path, n, status, verdict=None, checks=None, judge_log=None, framing=None, sheets=None):
    d = tmp_path / "art" / f"board-{n}"; (d / f"s{n}").mkdir(parents=True)
    (d / "status.json").write_text(json.dumps(dict(status, shot=n)))
    if verdict is not None: (d / "verdict.json").write_text(json.dumps(verdict))
    if checks: (d / "checks.log").write_text(checks)
    if judge_log: (d / "judge.log").write_text(judge_log)
    if framing: (d / f"s{n}" / "framing.json").write_text(json.dumps(framing))
    if sheets: (d / "preflight.json").write_text(json.dumps({"sheets": sheets}))
    return tmp_path / "art"


def test_the_collected_round_copies_verdicts_and_only_ever_adds_a_block(tmp_path, monkeypatch):
    import notes_ledger, preflight3d, rounds
    stories = tmp_path / "stories"; (stories / "s").mkdir(parents=True)
    for m in (board_ci, notes_ledger, preflight3d, rounds):
        monkeypatch.setattr(m, "STORIES", stories)
    ok = {"shot": 1, "score": 74, "scores": [70, 74, 80], "hard": [], "problems": [], "better": [], "pass": True}
    bad = {"shot": 2, "score": 55, "scores": [50, 55, 60], "hard": ["NOT THE WORLD: a bare backdrop"], "pass": False}
    art = _art(tmp_path, 1, {"stills": True, "judge_exit": 0}, {"shots": [ok], "panel": 3}, sheets={"aa": {"shot": 1, "at": "1"}})
    _art(tmp_path, 2, {"stills": True, "judge_exit": 2}, {"shots": [bad], "panel": 3})
    _art(tmp_path, 3, {"stills": False, "judge_exit": None}, checks="STAGING shot 3: back turned -> FAIL\nFAR shot 3: ok -> OK\n")
    _art(tmp_path, 4, {"stills": True, "judge_exit": 1}, judge_log="JUDGE3D: only 1 of 3 judges answered: no pass\n")
    _art(tmp_path, 6, {"stills": False, "judge_exit": None}, checks="BOARD s beat 1: x\nVARIETY s props: 'flag' is in beats [1, 2]\n")
    (tmp_path / "art" / "board-5").mkdir()                       # a cancelled job: no status, not in the round
    assert board_ci.apply("s", art, "ci board run 1") == 0
    v = {s["shot"]: s for s in json.loads((art / "board_verdict.json").read_text())["shots"]}
    assert sorted(v) == [1, 2, 3, 4, 6]
    assert any("VARIETY s props" in h for h in v[6]["hard"]), "a refusal that never says FAIL is still named (lava, run 45851683337)"
    assert v[1]["pass"] is True and v[1]["score"] == 74 and v[2]["hard"] == bad["hard"], "a verdict is copied, never regraded"
    assert v[3]["pass"] is False and v[3]["hard"] == ["a measured pre-check failed: STAGING shot 3: back turned -> FAIL"]
    assert v[4]["pass"] is False and v[4]["score"] is None and "no verdict" in v[4]["hard"][0]
    md = (stories / "s" / "judge_rounds.md").read_text()
    assert md.count("· storyboard ·") == 1 and "ci board run 1" in md, "one section for the round, as a session's round writes"
    assert "| 1 | 74 | 70, 74, 80 | PASS |" in md and "| 4 | None | - | FAIL |" in md
    led = json.loads((stories / "s" / "notes_ledger.json").read_text())
    assert led["rounds"] == 1 and "NOT THE WORLD" in led["shots"]["2"], "one round in the ledger, the panel's shots only"
    assert not {"3", "4", "6"} & set(led["shots"]), "a shot no panel graded is not a round of its notes"
    assert "aa" in json.loads((stories / "s" / "preflight.json").read_text())["sheets"]
    # dry: the same report, nothing written
    before = {p.name: p.read_text() for p in (stories / "s").iterdir()}
    assert board_ci.apply("s", art, "ci board run 2", dry=True) == 0
    assert {p.name: p.read_text() for p in (stories / "s").iterdir()} == before


def test_a_cross_shot_check_can_fail_a_shot_the_panel_passed_never_the_reverse(tmp_path, monkeypatch):
    import fresh, variety
    monkeypatch.setattr(variety, "held", lambda s: True); monkeypatch.setattr(fresh, "held", lambda s: False)
    monkeypatch.setattr(variety, "framing_problems", lambda fr: [(2, "framed like shot 1")] if set(fr) == {1, 2} else [])
    shots = [{"shot": 1, "score": 80, "pass": True, "hard": []}, {"shot": 2, "score": 75, "pass": True, "hard": []},
             {"shot": 3, "score": 40, "pass": False, "hard": ["BROKEN: x"]}]
    out = {s["shot"]: s for s in board_ci.add_blocks("s", shots, {1: {"h": 0.4}, 2: {"h": 0.4}, 9: {"h": 0.4}})}
    assert out[1]["pass"] is True and out[2]["pass"] is False and out[2]["hard"] == ["VARIETY: framed like shot 1"]
    assert out[3]["pass"] is False and out[3]["hard"] == ["BROKEN: x"]
    src = (STORE / "board_ci.py").read_text()
    assert not re.search(r'\[\s*"pass"\s*\]\s*=\s*True', src) and "PASS_SCORE =" not in src.replace('r"^PASS_SCORE = (\\d+)"', "")
