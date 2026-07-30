#!/usr/bin/env python3
"""The closed creative-improvement loop.

Drives render -> judge -> persist -> plan -> revise -> re-render -> re-judge ->
compare with injected fakes, so the whole control law is provable in a second
instead of three 90-minute CI renders."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import judge_loop as jl  # noqa: E402
from data_learning.judging_store import JudgingStore  # noqa: E402

POLICY = {**__import__("data_learning.judge_policy", fromlist=["x"]).DEFAULT_POLICY}


def _setup(root: Path):
    out = root / "curiosity_t.mp4"
    out.write_bytes(b"cut-0")
    (root / "curiosity_t_pkg").mkdir(exist_ok=True)
    return out


def _judges(script):
    """script: list of per-attempt taste dicts."""
    state = {"i": 0}

    def taste(out, ctx):
        v = script[min(state["i"], len(script) - 1)]
        state["i"] += 1
        return v
    return [
        jl.JudgeSpec("taste", taste, required=True, blind=True),
        jl.JudgeSpec("technical", lambda o, c: {"pass": True, "findings": []},
                     required=True),
        jl.JudgeSpec("factual", lambda o, c: {"pass": True, "findings": []},
                     required=True),
    ], state


def main():
    # ---------------------------------------------------------------- 1. PASS
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        judges, _ = _judges([{"pass": True, "overall_10": 9.3, "personality": 4,
                              "findings": []}])
        s = jl.run(out, render_fn=lambda a, p: {"ok": True, "director_rc": 0},
                   judges=judges, policy=POLICY, slug="t")
        assert s["status"] == "pass" and s["attempts"] == 1, s
        assert s["eligible_for_owner_review"] is True
        assert Path(d, "curiosity_t_pkg/judging/final_summary.json").exists()
        print("ok  1. a 9.3/10 clean film passes on attempt 1 and is persisted")

    # ------------------------------------------- 2. mediocre film cannot pass
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        judges, _ = _judges([{"pass": False, "overall_10": 3.0, "personality": 3,
                              "reject_labels": ["SAMENESS"],
                              "findings": [{"defect_code": "SAMENESS",
                                            "severity": "blocker",
                                            "target": "film",
                                            "complaint": "all alike"}]}])

        def render(attempt, plan):
            out.write_bytes(b"cut-" + str(attempt).encode())   # materially new
            return {"ok": True, "director_rc": 1}
        s = jl.run(out, render_fn=render, judges=judges, policy=POLICY, slug="t")
        assert s["status"] in ("quarantine", "abandoned"), s
        assert s["final_overall_10"] == 3.0
        assert s["attempts"] >= 2, "the loop gave up without escalating"
        print(f"ok  2. a 3.0/10 film never passes; loop ran {s['attempts']} "
              f"attempts -> {s['status']}")

    # ------------------------------------- 3. judge feedback becomes repairs
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        judges, _ = _judges([{"pass": False, "overall_10": 6.0, "personality": 3,
                              "findings": [
                                  {"defect_code": "STALE_SPAN", "severity": "major",
                                   "time_range": "88.5-96.0s",
                                   "complaint": "nothing new for 7.5s",
                                   "recommended_fix": "cut the hold"}]}])
        jl.run(out, render_fn=lambda a, p: {"ok": True, "director_rc": 3},
               judges=judges, policy={**POLICY, "max_attempts": 1}, slug="t")
        plan = JudgingStore(out).read(1, "repair_plan")
        assert plan["n_tasks"] == 1, plan
        t = plan["tasks"][0]
        assert t["defect_code"] == "STALE_SPAN"
        assert t["target"] == "88.5-96.0s"
        assert t["required_change"] == "cut the hold"
        assert t["evidence"]["complaint"] == "nothing new for 7.5s"
        print("ok  3. a judge complaint becomes a targeted repair task")

    # -------------------------------------------- 4. ESCALATION on a stall
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        same = {"pass": False, "overall_10": 6.0, "personality": 3,
                "findings": [{"defect_code": "SAMENESS", "severity": "blocker",
                              "target": "film", "complaint": "alike"}]}
        judges, _ = _judges([same, same, same])

        def render(attempt, plan):
            out.write_bytes(b"cut-" + str(attempt).encode())
            return {"ok": True, "director_rc": 1}
        s = jl.run(out, render_fn=render, judges=judges, policy=POLICY, slug="t")
        esc = s["escalation_progression"]
        assert esc[0] == "local", esc
        assert "scene" in esc or "structural" in esc, esc
        assert s["status"] == "abandoned", s
        print(f"ok  4. an unmoving score escalates {' -> '.join(esc)} "
              "and ends in abandonment, not endless polish")

    # ------------------------------ 5. a re-render that changes NOTHING stalls
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        v = {"pass": False, "overall_10": 6.0, "personality": 3, "findings": []}
        judges, _ = _judges([v, v])
        s = jl.run(out, render_fn=lambda a, p: {"ok": True, "director_rc": 0},
                   judges=judges, policy={**POLICY, "max_attempts": 2}, slug="t")
        c = s["attempts_detail"][1]["comparison"]
        assert c["materially_different"] is False, c
        assert c["stalled"] is True, c
        print("ok  5. an identical re-render is NOT counted as a repair")

    # ----------------------------------- 6. improvement is measured, not claimed
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        judges, _ = _judges([
            {"pass": False, "overall_10": 6.0, "personality": 3,
             "findings": [{"defect_code": "STALE_SPAN", "severity": "major",
                           "target": "88.5-96.0s", "complaint": "hold"}]},
            {"pass": False, "overall_10": 8.4, "personality": 4,
             "findings": [{"defect_code": "CAPTIONS", "severity": "minor",
                           "target": "film", "complaint": "long line"}]},
        ])

        def render(attempt, plan):
            out.write_bytes(b"cut-" + str(attempt).encode())
            return {"ok": True, "director_rc": 0}
        s = jl.run(out, render_fn=render, judges=judges,
                   policy={**POLICY, "max_attempts": 2}, slug="t")
        c = s["attempts_detail"][1]["comparison"]
        assert c["overall_delta"] == 2.4, c
        assert c["materially_different"] is True
        assert "STALE_SPAN@88.5-96.0s" in c["fixed"], c
        assert "STALE_SPAN@88.5-96.0s" in c["targeted_defects_fixed"], c
        assert "CAPTIONS@film" in c["introduced"], c
        assert c["stalled"] is False
        assert s["score_progression"] == [6.0, 8.4]
        print("ok  6. before/after: delta +2.4, targeted defect fixed, "
              "new defect surfaced as introduced")

    # -------------------------- 7. a required judge that fails blocks the pass
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))

        def boom(o, c):
            raise RuntimeError("judge crashed")
        judges = [
            jl.JudgeSpec("taste", lambda o, c: {"pass": True, "overall_10": 9.9,
                                                "personality": 5, "findings": []},
                         required=True),
            jl.JudgeSpec("technical", boom, required=True),
            jl.JudgeSpec("factual", lambda o, c: None, required=True),
        ]
        s = jl.run(out, render_fn=lambda a, p: {"ok": True, "director_rc": 0},
                   judges=judges, policy={**POLICY, "max_attempts": 1}, slug="t")
        assert s["status"] != "pass", s
        blockers = " ".join(s["unresolved_blockers"])
        assert "technical" in blockers and "factual" in blockers, blockers
        store = JudgingStore(out)
        assert store.normalized(1)["technical"]["status"] == "failed"
        assert store.normalized(1)["factual"]["status"] == "abstained"
        print("ok  7. a 9.9/10 film still fails closed when required judges "
              "crash or abstain — and both are persisted")

    # --------------------------------- 8. blind judges never see prior context
    with tempfile.TemporaryDirectory() as d:
        out = _setup(Path(d))
        seen = {}

        def spy(o, ctx):
            seen.update(ctx)
            return {"pass": True, "overall_10": 9.5, "personality": 5,
                    "findings": []}
        judges = [jl.JudgeSpec("taste", spy, required=True, blind=True),
                  jl.JudgeSpec("technical", lambda o, c: {"pass": True}, required=True),
                  jl.JudgeSpec("factual", lambda o, c: {"pass": True}, required=True)]
        jl.run(out, render_fn=lambda a, p: {"ok": True, "director_rc": 0},
               judges=judges, policy={**POLICY, "max_attempts": 1}, slug="t",
               ctx={"out": str(out), "pkg": "p", "story": {"slug": "secret"},
                    "expected_verdict": "pass", "previous_score": 3.0})
        assert set(seen) <= {"out", "pkg"}, seen
        print("ok  8. a blind judge receives no intent, story or prior score")

    print("judge loop: 8/8 checks pass")


if __name__ == "__main__":
    main()
