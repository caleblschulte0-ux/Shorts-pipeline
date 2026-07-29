#!/usr/bin/env python3
"""Tests for the last-line publish guards (PR#173 adoptions): the manifest-
bound owner approval and the kill switch. Contract: an approval is a statement
about ONE exact cut — any re-render or artifact change makes it inert — and
the kill switch outranks everything."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import approve_publish as apv   # noqa: E402
import artifact_identity as ai  # noqa: E402


def build_pass_package(td: Path) -> Path:
    out = td / "film.mp4"
    pkg = td / "film_pkg"
    pkg.mkdir()
    out.write_bytes(b"CUT-ONE" * 4096)
    out.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n")
    out.with_suffix(".jpg").write_bytes(b"J")
    out.with_suffix(".meta.json").write_text("{}")
    (pkg / "fallbacks.json").write_text('{"verdict": "ok", "fallbacks": []}')
    ai.build_manifest(out, director_rc=0)
    (pkg / "produce_report.json").write_text(json.dumps(
        {"status": "pass", "reasons": []}))
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        out = build_pass_package(td)

        ok, why = apv.check_approval(out)
        assert not ok and "no owner approval" in why, why
        print("ok  1. unapproved package is not publishable")

        apv.approve(out)
        ok, why = apv.check_approval(out)
        assert ok, why
        print("ok  2. approve() then check_approval() -> approved")

        # re-render: new video bytes -> new manifest -> old approval inert
        out.write_bytes(b"CUT-TWO-rerendered" * 4096)
        ai.build_manifest(out, director_rc=0)
        ok, why = apv.check_approval(out)
        assert not ok and "DIFFERENT package" in why, why
        print("ok  3. approval does NOT survive a re-render (bound to old manifest)")

        # artifact swap after approval (manifest unchanged) -> refused
        apv.approve(out)
        out.with_suffix(".jpg").write_bytes(b"SWAPPED-THUMB")
        ok, why = apv.check_approval(out)
        assert not ok and "changed since its manifest" in why, why
        print("ok  4. artifact swap after approval -> refused")

    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        out = td / "film.mp4"
        pkg = td / "film_pkg"
        pkg.mkdir()
        out.write_bytes(b"Q" * 2048)
        ai.build_manifest(out, director_rc=3)
        (pkg / "produce_report.json").write_text(json.dumps(
            {"status": "quarantine", "reasons": ["director gates failed"]}))
        try:
            apv.approve(out)
            raise AssertionError("approved a QUARANTINED package")
        except SystemExit as e:
            assert "quarantined" in str(e).lower() or "quarantine" in str(e), e
        print("ok  5. a quarantined film cannot be approved")

    # kill switch
    real = apv.KILL_SWITCH
    with tempfile.TemporaryDirectory() as d:
        apv.KILL_SWITCH = Path(d) / "curiosity_kill_switch"
        assert apv.kill_switch_engaged() is None
        apv.KILL_SWITCH.write_text("owner said stop\n")
        msg = apv.kill_switch_engaged()
        assert msg and "owner said stop" in msg, msg
        print("ok  6. kill-switch file halts uploads, reason surfaced")
    apv.KILL_SWITCH = real

    print("publish guards: 6/6 tests pass")


if __name__ == "__main__":
    main()
