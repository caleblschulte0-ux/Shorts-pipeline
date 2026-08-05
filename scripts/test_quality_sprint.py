#!/usr/bin/env python3
"""The sprint loop must record itself, or it records nothing.

RULE ZERO (CLAUDE.md): a capability nothing calls is not a capability. The
five ledger rows from the 2026-08-01/02 sprint had to be RECONSTRUCTED by hand
from `performance.json` a day later, which is exactly why two regressions ran
unnoticed for a day. If recording depends on someone remembering to run a
command after a four-hour render, it will be forgotten the first time a render
fails at 3am — and the sprint that was supposed to prove improvement will have
no evidence that anything changed at all.

So `produce()` records every render itself. These tests hold that: the row is
written from the package the render already produced, and a metrics failure
never costs a render.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import film_metrics as fm  # noqa: E402
import produce  # noqa: E402


def _pkg(d: Path, *, metrics=True, verdict=True) -> Path:
    pkg = d / "curiosity_x_pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    if metrics:
        (pkg / "plan_metrics.json").write_text(json.dumps(
            {"shots": 39, "figure_shots": 10, "card_fraction": 0.0,
             "summary": "39 shots · figure 10"}))
    if verdict:
        (pkg / "verdict.json").write_text(json.dumps(
            {"pass": False, "overall_10": 4.5, "personality": 3,
             "reject_labels": ["SAMENESS"]}))
    return pkg


def test_a_render_records_itself():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        pkg = _pkg(d)
        led = d / "led.jsonl"
        old, fm.LEDGER = fm.LEDGER, led
        try:
            produce._record_quality("x", d / "curiosity_x.mp4", pkg,
                                    {"status": "quarantine"})
        finally:
            fm.LEDGER = old
        rows = fm.history(led)
        assert len(rows) == 1, rows
        r = rows[0]
        assert r["slug"] == "x" and r["figure_shots"] == 10, r
        assert r["overall_10"] == 4.5 and r["personality"] == 3, r
        assert r["reject_labels"] == ["SAMENESS"], r
        assert r["note"] == "quarantine", r
    print("ok  a finished render appends its own plan + verdict to the ledger")


def test_a_broken_ledger_never_costs_a_render():
    """Four hours of runner time must not be lost to a metrics bug."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        pkg = _pkg(d)
        (pkg / "plan_metrics.json").write_text("{ not json")
        produce._record_quality("x", d / "curiosity_x.mp4", pkg, {})
        # ...and a package with no metrics at all is simply skipped, not faked
        pkg2 = _pkg(d / "b", metrics=False)
        led = d / "led.jsonl"
        old, fm.LEDGER = fm.LEDGER, led
        try:
            produce._record_quality("x", d / "b" / "curiosity_x.mp4", pkg2, {})
        finally:
            fm.LEDGER = old
        assert fm.history(led) == [], "a blank row teaches nothing; write none"
    print("ok  measurement failure is non-fatal, and never invents a row")


def test_produce_actually_calls_it():
    """Wiring, not just the function — the exact thing rule zero forbids."""
    src = (REPO / "scripts" / "produce.py").read_text()
    assert "_record_quality(slug, out, pkg, result)" in src, (
        "produce() must record every render; a ledger filled by hand after "
        "the fact is how the last sprint lost its evidence")
    print("ok  produce() calls the recorder on every render")


def test_a_fixture_render_cannot_pollute_the_STANDING_ledger():
    """The CI smoke runs the REAL producer on a throwaway fixture.

    Once `produce()` started recording every render by itself, the first smoke
    after that wrote a `zz-ci-smoke` row into the standing ledger — and every
    CI run would have added one. `trend()` averages whatever it finds, so a
    window of fixture scores would have been reported as the channel's
    quality. That is the failure mode this whole system exists against: a
    number that looks like evidence and is not.
    """
    import os
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "throwaway.jsonl"
        old = os.environ.get("CURIOSITY_QUALITY_LEDGER")
        os.environ["CURIOSITY_QUALITY_LEDGER"] = str(f)
        try:
            assert fm.ledger_path() == f, fm.ledger_path()
            fm.record("zz-ci-smoke", fm.score_plan(
                [{"kind": "depict", "seconds": 4.0}]))
            assert f.exists() and len(fm.history(f)) == 1
        finally:
            if old is None:
                os.environ.pop("CURIOSITY_QUALITY_LEDGER", None)
            else:
                os.environ["CURIOSITY_QUALITY_LEDGER"] = old
        assert fm.ledger_path() == fm.LEDGER, "the override must not stick"
    # ...and the smoke actually sets it, rather than this just being possible
    src = (REPO / "scripts" / "producer_smoke.py").read_text()
    assert 'os.environ["CURIOSITY_QUALITY_LEDGER"]' in src, (
        "producer_smoke must redirect the ledger; a capability nothing calls "
        "is not a capability")
    # ...and no fixture row survives in the real one
    for r in fm.history():
        assert not str(r.get("slug", "")).startswith("zz-"), (
            f"a fixture row is in the standing ledger: {r.get('slug')}")
    print("ok  fixture renders go to a temp ledger, and the record is clean")


def test_the_driver_runs():
    """Each subcommand must at least execute against the real ledger."""
    import subprocess
    for argv in (["status"], ["next"], ["next", "shared-air"]):
        r = subprocess.run([sys.executable, "scripts/quality_sprint.py", *argv],
                           capture_output=True, text=True, cwd=REPO)
        assert r.returncode == 0, (argv, r.stdout, r.stderr)
        assert r.stdout.strip(), argv
    print("ok  status / next run against the live ledger")


if __name__ == "__main__":
    test_a_render_records_itself()
    test_a_broken_ledger_never_costs_a_render()
    test_produce_actually_calls_it()
    test_a_fixture_render_cannot_pollute_the_STANDING_ledger()
    test_the_driver_runs()
    print("all quality-sprint checks pass")
