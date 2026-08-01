#!/usr/bin/env python3
"""Durable judging evidence.

    A judge response that cannot be viewed after the runner disappears is
    treated as MISSING judge evidence.

These tests hold that line: nothing is overwritten, failures and abstentions
are recorded rather than omitted, and every response is bound to the exact
artifact it judged so a re-render invalidates stale evidence by construction.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning.judging_store import JudgingStore  # noqa: E402


def _mk(root: Path, data=b"video-one") -> Path:
    out = root / "curiosity_x.mp4"
    out.write_bytes(data)
    (root / "curiosity_x_pkg").mkdir(exist_ok=True)
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        out = _mk(root)
        s = JudgingStore(out)

        # 1. attempts are append-only and never reused
        a1 = s.open_attempt(policy={"development_min_overall": 8.0})
        assert a1 == 1 and s.attempt_dir(1).exists()
        assert s.next_attempt() == 2
        try:
            s.open_attempt(1)
            raise AssertionError("re-opening attempt 1 must be refused")
        except FileExistsError:
            pass
        print("ok  1. attempt dirs are append-only; reuse is refused")

        # 2. raw AND normalized are both persisted, verbatim raw
        raw = {"pass": False, "personality": 3, "overall_10": 3.0,
               "one_line": "watermarked stock", "vendor_extra": {"nested": [1, 2]}}
        s.record(a1, "taste", raw=raw,
                 normalized={"pass": False, "overall_10": 3.0,
                             "findings": [{"defect_code": "SAMENESS"}]},
                 model="opus", provider="vision_subagent", rubric_version="v1")
        rawdoc = json.loads((s.attempt_dir(a1) / "taste_raw.json").read_text())
        assert rawdoc["response"] == raw, "raw response was altered"
        assert rawdoc["model"] == "opus" and rawdoc["rubric_version"] == "v1"
        norm = json.loads((s.attempt_dir(a1) / "taste_normalized.json").read_text())
        assert norm["overall_10"] == 3.0 and norm["findings"]
        print("ok  2. raw is stored verbatim beside the normalized form")

        # 3. a FAILED and an ABSTAINED judge are recorded, not omitted
        s.record(a1, "factual", raw={"error": "gate crashed"}, status="failed",
                 error="gate crashed")
        s.record(a1, "hook", raw=None, status="abstained")
        got = s.normalized(a1)
        assert got["factual"]["status"] == "failed"
        assert got["factual"]["pass"] is None
        assert got["hook"]["status"] == "abstained"
        assert set(got) == {"taste", "factual", "hook"}
        print("ok  3. failures and abstentions are recorded as evidence")

        # 4. every response is bound to the exact artifact judged
        assert norm["mp4_sha256"], "no artifact binding on the response"
        assert s.evidence_for(a1, "taste") is not None
        print("ok  4. responses carry the judged artifact's sha256")

        # 5. a CHANGED video invalidates the old evidence by construction
        out.write_bytes(b"video-two-different")
        assert s.evidence_for(a1, "taste") is None, \
            "stale evidence survived a re-render"
        print("ok  5. a changed render invalidates prior judge evidence")

        # 6. a second attempt does not touch the first
        a2 = s.open_attempt(escalation="scene")
        assert a2 == 2
        s.record(a2, "taste", raw={"overall_10": 8.6},
                 normalized={"overall_10": 8.6, "pass": True})
        assert json.loads((s.attempt_dir(1) / "taste_raw.json").read_text()
                          )["response"] == raw, "attempt 1 was mutated"
        assert s.existing_attempts() == [1, 2]
        print("ok  6. a later attempt never overwrites an earlier one")

        # 7. history reads back in order with the identity manifests
        s.write(a1, "combined_verdict", {"overall_10": 3.0})
        s.write(a2, "combined_verdict", {"overall_10": 8.6})
        hist = s.history()
        assert [h["attempt"] for h in hist] == [1, 2]
        assert hist[1]["manifest"]["escalation"] == "scene"
        assert [h["combined"]["overall_10"] for h in hist] == [3.0, 8.6]
        print("ok  7. history replays every attempt with its identity manifest")

        # 8. the whole thing is small JSON — safe to upload, no media
        for p in s.root.rglob("*"):
            if p.is_file():
                assert p.suffix == ".json", f"non-JSON in judging evidence: {p}"
                assert p.stat().st_size < 256_000, f"{p} too large for git/artifact"
        print("ok  8. evidence is small JSON only (no media, artifact-safe)")

    print("judging store: 8/8 checks pass")


if __name__ == "__main__":
    main()
