#!/usr/bin/env python3
"""The three visibility surfaces. A green workflow with no readable judge
evidence is not acceptable — these tests prove the evidence is there."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import judge_report  # noqa: E402
from data_learning import judge_loop as jl  # noqa: E402
from data_learning.judge_policy import DEFAULT_POLICY  # noqa: E402
from data_learning.judging_store import JudgingStore  # noqa: E402


def _drive(root: Path):
    """Two attempts: a bad cut that improves but still fails."""
    out = root / "curiosity_r.mp4"
    out.write_bytes(b"cut-0")
    (root / "curiosity_r_pkg").mkdir(exist_ok=True)
    script = [
        {"pass": False, "overall_10": 5.0, "personality": 3,
         "reject_labels": ["SAMENESS"],
         "findings": [{"defect_code": "SAMENESS", "severity": "blocker",
                       "target": "beat 12", "complaint": "every shot alike",
                       "recommended_fix": "vary composition"}]},
        {"pass": False, "overall_10": 7.9, "personality": 4,
         "findings": [{"defect_code": "STALE_SPAN", "severity": "major",
                       "time_range": "88.5-96.0s",
                       "complaint": "nothing new for 7.5s",
                       "recommended_fix": "cut the hold"}]},
    ]
    state = {"i": 0}

    def taste(o, c):
        v = script[min(state["i"], len(script) - 1)]
        state["i"] += 1
        return v

    def render(attempt, plan):
        out.write_bytes(b"cut-" + str(attempt).encode())
        return {"ok": True, "director_rc": 1}

    judges = [jl.JudgeSpec("taste", taste, required=True, blind=True,
                           model="opus", provider="vision_subagent"),
              jl.JudgeSpec("technical", lambda o, c: {"pass": True, "findings": []},
                           required=True),
              jl.JudgeSpec("factual", lambda o, c: None, required=True)]
    jl.run(out, render_fn=render, judges=judges,
           policy={**DEFAULT_POLICY, "max_attempts": 2}, slug="r")
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        out = _drive(root)
        summary_file = root / "step_summary.md"
        os.environ["GITHUB_STEP_SUMMARY"] = str(summary_file)
        try:
            res = judge_report.write_all(out)
        finally:
            del os.environ["GITHUB_STEP_SUMMARY"]

        store = JudgingStore(out)

        # A. machine-readable package — raw AND normalized, per attempt, kept
        for n in (1, 2):
            d_ = store.attempt_dir(n)
            assert (d_ / "taste_raw.json").exists(), n
            assert (d_ / "taste_normalized.json").exists(), n
            assert (d_ / "combined_verdict.json").exists(), n
            assert (d_ / "repair_plan.json").exists(), n
            assert (d_ / "manifest.json").exists(), n
        assert (store.root / "final_summary.json").exists()
        # the abstaining required judge is on disk, not omitted
        assert store.normalized(1)["factual"]["status"] == "abstained"
        print("ok  A. every attempt has raw + normalized + combined + plan + "
              "manifest, including the abstention")

        # B. human report — the specific things the owner asked to see
        md = (store.root / "report.md").read_text()
        for must in ("Judging report", "Scores by judge", "Every complaint",
                     "Repair plan", "Movement vs the previous attempt",
                     "every shot alike", "vary composition",
                     "beat 12", "88.5-96.0s", "SAMENESS", "STALE_SPAN",
                     "abstained"):
            assert must in md, f"report.md is missing {must!r}"
        assert "5.0" in md and "7.9" in md, "score progression missing"
        assert "+2.90" in md or "+2.9" in md, "before/after delta missing"
        assert (store.root / "report.html").exists()
        print("ok  B. report.md carries scores, every complaint, worst beats, "
              "the repair asked for, and the before/after movement")

        # C. Actions step summary — concise, with the artifact name
        txt = summary_file.read_text()
        for must in ("Judging", "attempt", "overall", judge_report.ARTIFACT_NAME):
            assert must in txt, f"step summary missing {must!r}"
        assert "ABANDONED" in txt or "QUARANTINE" in txt, txt[:200]
        assert len(txt) < 20_000, "step summary should stay concise"
        print(f"ok  C. GITHUB_STEP_SUMMARY written ({len(txt)} chars) with the "
              f"{judge_report.ARTIFACT_NAME!r} artifact name")

        # the report is derived purely from durable files — no runner needed
        assert all(Path(p).exists() for p in res["written"][:2])
        fs = json.loads((store.root / "final_summary.json").read_text())
        assert fs["score_progression"] == [5.0, 7.9], fs
        assert fs["autonomous_publish_allowed"] is False
        print("ok  D. the whole report regenerates from the package alone")

    print("judge report: 4/4 surfaces verified")


if __name__ == "__main__":
    main()
