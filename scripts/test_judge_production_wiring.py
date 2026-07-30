#!/usr/bin/env python3
"""PRODUCTION wiring for the closed judging loop.

Unit tests prove the machinery. These prove the machinery is actually in the
path a real render takes — call sites, not commit claims."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import produce  # noqa: E402


def _fixture(root: Path, *, verdict: dict | None):
    out = root / "curiosity_w.mp4"
    out.write_bytes(b"\x00" * 4096)
    pkg = root / "curiosity_w_pkg"
    pkg.mkdir()
    out.with_suffix(".meta.json").write_text("{}")
    out.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
    out.with_suffix(".jpg").write_bytes(b"\xff\xd8jpg")
    (pkg / "fallbacks.json").write_text('{"verdict": "ok", "fallbacks": []}')
    if verdict is not None:
        import artifact_identity
        v = dict(verdict)
        v["mp4_sha256"] = artifact_identity.sha256_file(out)
        (pkg / "verdict.json").write_text(json.dumps(v))
    return out


def main():
    src = (REPO / "scripts" / "produce.py").read_text()

    # 1. the binding policy is called from produce.evaluate — not just imported
    assert "judge_policy.decide(" in src, \
        "produce.evaluate does not consult the binding quality policy"
    assert 'reasons.extend(policy_decision["blockers"])' in src, \
        "the policy decision is computed but never blocks the gate"
    assert "record_judging" in src
    print("ok  1. produce.evaluate calls judge_policy.decide and extends the "
          "quarantine reasons with its blockers")

    # 2. the OLD weak rule is gone from the gate
    assert 'not verdict.get("pass")' not in src, \
        "the old pass-boolean gate is still the deciding check"
    print("ok  2. the old 'no labels + personality>=3' gate no longer decides")

    # 3. a mediocre-but-labelless verdict is REFUSED end to end
    with tempfile.TemporaryDirectory() as d:
        out = _fixture(Path(d), verdict={
            "pass": True, "reject_labels": [], "personality": 3.0,
            "overall_10": 3.0, "one_line": "flat", "worst_beat": "beat 4",
            "fix": "give it a character"})
        res = produce.evaluate(out, director_rc=0)
        assert res["status"] == "quarantine", res
        assert any("below the development floor" in r for r in res["reasons"]), res
        assert res["judge_policy"]["band"] == "structural_failure"
        print("ok  3. a 3.0/10 verdict with NO reject labels and personality 3 "
              "is quarantined in production (it used to PASS)")

    # 4. a genuinely good verdict still passes
    with tempfile.TemporaryDirectory() as d:
        out = _fixture(Path(d), verdict={
            "pass": True, "reject_labels": [], "personality": 4.0,
            "overall_10": 9.4, "one_line": "good", "worst_beat": "", "fix": ""})
        res = produce.evaluate(out, director_rc=0)
        assert res["status"] == "pass", res
        assert res["judge_policy"]["eligible_for_owner_review"] is True
        assert res["judge_policy"]["autonomous_publish_allowed"] is False
        print("ok  4. a 9.4/10 verdict passes and is owner-review eligible, "
              "with autonomous publishing still off")

    # 5. a verdict with NO overall_10 fails closed (missing evidence)
    with tempfile.TemporaryDirectory() as d:
        out = _fixture(Path(d), verdict={
            "pass": True, "reject_labels": [], "personality": 5.0})
        res = produce.evaluate(out, director_rc=0)
        assert res["status"] == "quarantine", res
        assert any("overall_10" in r for r in res["reasons"]), res
        print("ok  5. a verdict without a professional-quality score fails closed")

    # 6. record_judging persists the full evidence tree for a real render
    with tempfile.TemporaryDirectory() as d:
        out = _fixture(Path(d), verdict={
            "pass": False, "reject_labels": ["SAMENESS"], "personality": 3.0,
            "overall_10": 4.0, "one_line": "same", "worst_beat": "beat 7",
            "fix": "vary it"})
        info = produce.record_judging("w", out, story={}, director_rc=1)
        root = Path(info["judging_dir"])
        assert (root / "attempt_01" / "taste_raw.json").exists()
        assert (root / "attempt_01" / "combined_verdict.json").exists()
        assert (root / "attempt_01" / "repair_plan.json").exists()
        assert (root / "final_summary.json").exists()
        assert (root / "report.md").exists()
        plan = json.loads((root / "attempt_01" / "repair_plan.json").read_text())
        # the taste judge's finding becomes a real task; at the LOCAL class it
        # sits in `deferred` with the class that unlocks it (the ladder), which
        # is exactly the designed behaviour — it is never dropped.
        sam = [t for t in plan["tasks"] + plan["deferred"]
               if t["defect_code"] == "SAMENESS"]
        assert sam and sam[0]["target"] == "beat 7", plan
        assert sam[0]["required_change"] == "vary it", sam
        assert sam[0].get("unlocks_at_class") == "scene", sam
        assert info["overall_10"] == 4.0 and not info["advance"]
        # a second call APPENDS rather than overwriting
        info2 = produce.record_judging("w", out, story={}, director_rc=1)
        assert info2["attempt"] == 2
        assert (root / "attempt_01" / "taste_raw.json").exists()
        print("ok  6. record_judging writes the full evidence tree and the "
              "second call appends attempt_02 without touching attempt_01")

    # 7. produce() calls record_judging on every real render
    assert "result[\"judging\"] = record_judging(" in src, \
        "produce() does not capture judging evidence for real renders"
    print("ok  7. produce() captures judging evidence on every render")

    # 8. CI uploads the evidence and writes a step summary
    wf = (REPO / ".github" / "workflows" / "curiosity.yml").read_text()
    assert "curiosity-judging" in wf, \
        "CI does not upload the judging evidence artifact — it would die with "\
        "the runner, which is the exact failure this work exists to fix"
    assert "_pkg/judging/**" in wf, \
        "the judging artifact upload does not include the evidence tree"
    assert "judge_report.py" in wf, "CI never writes the judge step summary"
    print("ok  8. CI uploads 'curiosity-judging' and writes the step summary")

    print("judge production wiring: 8/8 checks pass")


if __name__ == "__main__":
    main()
