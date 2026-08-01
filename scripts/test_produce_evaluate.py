#!/usr/bin/env python3
"""Unit tests for the producer decision layer (produce.evaluate) — the gate
that turns a finished render + its packaged evidence into PASS or QUARANTINE.

Every scenario builds a synthetic package on disk (no rendering, no network):
mp4 stub + _pkg/ + sidecars, then asserts the decision and its reasons.
Verdicts are written through judge_verdict.write so they carry the mp4 hash
binding the evaluate() law now requires (PR#173 adoption A).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import judge_verdict as jv  # noqa: E402
import produce              # noqa: E402

GOOD_VERDICT = {"pass": True, "reject_labels": [], "personality": 4.0,
                "overall_10": 9.3,
                "card_fraction_estimate": 0.2, "one_line": "t"}


def build_pkg(td: Path, *, verdict=GOOD_VERDICT, fallbacks=None,
              sidecars=True) -> Path:
    out = td / "film.mp4"
    pkg = td / "film_pkg"
    pkg.mkdir(exist_ok=True)
    if fallbacks is not None:
        (pkg / "fallbacks.json").write_text(json.dumps(fallbacks))
    out.write_bytes(b"x" * 2048)
    if sidecars:
        out.with_suffix(".meta.json").write_text("{}")
        out.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n")
        out.with_suffix(".jpg").write_bytes(b"j")
    if verdict is not None:
        jv.write(out, dict(verdict))      # binds mp4_sha256 to the stub video
    return out


def main():
    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td), fallbacks={"verdict": "ok", "fallbacks": []})
        res = produce.evaluate(out, 0)
        assert res["status"] == "pass" and res["reasons"] == [], res
        print("ok  1. clean package + bound verdict + rc=0 -> PASS")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td), verdict=None)
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("no vision taste verdict" in r for r in res["reasons"]), res
        print("ok  2. missing verdict FAILS CLOSED")

    with tempfile.TemporaryDirectory() as td:
        # belt-and-braces mtime rule: hash still matches (content unchanged)
        # but the mp4's mtime is bumped AFTER the verdict was written.
        out = build_pkg(Path(td))
        time.sleep(0.02)
        os.utime(out)
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("stale" in r.lower() for r in res["reasons"]), res
        print("ok  3. mp4 newer than verdict (secondary mtime rule) -> stale")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td), verdict={**GOOD_VERDICT, "pass": False,
                                           "personality": 1.0, "overall_10": 2.0,
                                           "reject_labels": ["SAMENESS"]})
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("hard objection" in r for r in res["reasons"]), res
        assert any("below the development floor" in r
                   for r in res["reasons"]), res
        print("ok  4. taste REJECT quarantines (hard objection + score floor)")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td), fallbacks={
            "verdict": "unacceptable",
            "fallbacks": [{"kind": "narration_to_silence",
                           "severity": "unacceptable"}]})
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("unacceptable" in r for r in res["reasons"]), res
        print("ok  5. unacceptable fallback quarantines")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td), sidecars=False)
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert sum("missing publishing sidecar" in r for r in res["reasons"]) == 3
        print("ok  6. missing meta/srt/jpg sidecars quarantine")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td))
        res = produce.evaluate(out, 3)
        assert res["status"] == "quarantine"
        assert any("director gates failed" in r for r in res["reasons"]), res
        print("ok  7. director rc!=0 quarantines")

    with tempfile.TemporaryDirectory() as td:
        out = build_pkg(Path(td))
        res = produce.evaluate(out, 0,
                               story={"require_provenance": True,
                                      "slug": "no-such-slug-zz"})
        assert res["status"] == "quarantine"
        assert any("facts gate" in r.lower() for r in res["reasons"]), res
        print("ok  8. provenance story with a broken facts gate fails closed")

    print("produce.evaluate: 8/8 scenarios pass")


if __name__ == "__main__":
    main()
