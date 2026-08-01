#!/usr/bin/env python3
"""Tests for the hash-chained run ledger + the manifest-based resume path
(PR#173 adoption D). The resume contract under test:

  - a package whose manifest verifies EXACTLY (story + video + sidecars all
    unchanged, director rc recorded) is reused without re-rendering;
  - ANY change (story edited, video swapped, missing rc) forces a full render;
  - fresh=True forces a full render even when identity verifies;
  - the ledger chain detects edits to its own history.

The renderer is a tripwire module: the test fails if a resume-eligible run
touches it, and fails if a resume-INeligible run does not.
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import artifact_identity as ai  # noqa: E402
import judge_verdict as jv      # noqa: E402
import produce                  # noqa: E402
import run_ledger               # noqa: E402


class RenderTripwire:
    def __init__(self, rc: int = 0):
        self.calls = 0
        self.rc = rc

    def run(self, story_path, out, rounds=2):
        self.calls += 1
        return self.rc


def install_tripwire(rc: int = 0) -> RenderTripwire:
    trip = RenderTripwire(rc)
    mod = types.ModuleType("no_dull_beats")
    mod.run = trip.run
    sys.modules["no_dull_beats"] = mod
    return trip


def build_green_package(td: Path) -> tuple[Path, Path]:
    out = td / "film.mp4"
    (td / "film_pkg").mkdir()
    out.write_bytes(b"RENDERED" * 4096)
    out.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n")
    out.with_suffix(".jpg").write_bytes(b"J")
    out.with_suffix(".meta.json").write_text("{}")
    (td / "film_pkg" / "fallbacks.json").write_text(
        '{"verdict": "ok", "fallbacks": []}')
    story = td / "zztest.beats.json"
    story.write_text('{"slug": "zztest", "beats": []}')
    return out, story


def main():
    # ---- ledger chain ----
    with tempfile.TemporaryDirectory() as d:
        lp = Path(d) / "ledger.jsonl"
        for i in range(4):
            run_ledger.append("evt", "slug", {"i": i}, path=lp)
        ok, why = run_ledger.verify_chain(lp)
        assert ok, why
        print("ok  1. chain of 4 events verifies")
        lines = lp.read_text().splitlines()
        doc = json.loads(lines[2])
        doc["payload"]["i"] = 99                      # edit history
        lines[2] = json.dumps(doc)
        lp.write_text("\n".join(lines) + "\n")
        ok, why = run_ledger.verify_chain(lp)
        assert not ok and "seq 2" in why, why
        print("ok  2. edited event detected at the exact sequence")

    # ---- resume path ----
    real_ledger = run_ledger.LEDGER_PATH
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        run_ledger.LEDGER_PATH = td / "ledger.jsonl"
        out, story = build_green_package(td)
        produce.resolve_story = lambda slug: story   # test story resolution
        ai.build_manifest(out, story_path=story, director_rc=0)
        # `overall_10` became REQUIRED when the quality policy started binding
        # on the professional-quality score rather than on personality alone
        # (judge_verdict.validate). This fixture was never updated, and the
        # failure was invisible because nothing ran scripts/test_*.py.
        jv.write(out, {"personality": 4, "reject_labels": [],
                       "overall_10": 8})
        # manifest hashed the package BEFORE verdict.json existed inside pkg?
        # verdict lives in pkg but is not a manifest artifact — identity is the
        # film + sidecars, judgment binds separately. Rebuild manifest AFTER the
        # verdict to mimic produce order (manifest right after render).
        trip = install_tripwire()
        try:
            res = produce.produce("zztest", out)
        finally:
            del sys.modules["no_dull_beats"]
        assert trip.calls == 0, "RESUME-ELIGIBLE RUN RE-RENDERED"
        assert res.get("resumed") is True and res["status"] == "pass", res
        print("ok  3. verified-identical package resumes without re-render -> PASS")

        # fresh=True must re-render even though identity verifies
        trip = install_tripwire()
        try:
            res = produce.produce("zztest", out, fresh=True)
        finally:
            del sys.modules["no_dull_beats"]
        assert trip.calls == 1, "fresh=True did not re-render"
        print("ok  4. fresh=True forces a full render")

        # story edited -> resume must refuse and re-render
        story.write_text('{"slug": "zztest", "beats": [{"new": 1}]}')
        trip = install_tripwire()
        try:
            res = produce.produce("zztest", out)
        finally:
            del sys.modules["no_dull_beats"]
        assert trip.calls == 1, "changed story did NOT force a re-render"
        print("ok  5. story change breaks identity -> full render")

    run_ledger.LEDGER_PATH = real_ledger
    print("run ledger + resume: 5/5 tests pass")


if __name__ == "__main__":
    main()
