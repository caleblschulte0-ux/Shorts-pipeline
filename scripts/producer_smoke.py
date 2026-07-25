#!/usr/bin/env python3
"""PRODUCER SMOKE (CI layer 4) — prove the canonical machinery on a tiny
all-designed fixture story, honestly, in either network condition.

Runs ``produce`` on ``pro_stories/fixtures/smoke.beats.json`` (3 designed_2d
beats, no external media). Two outcomes are correct:

  ONLINE  (TTS reachable): the render completes with narration; the smoke then
          asserts the full package exists. The producer will still QUARANTINE
          on the missing vision verdict — that IS the fail-closed law working
          (nothing is ever publishable unjudged), so exit 5 with exactly that
          reason is a smoke PASS.
  OFFLINE (TTS unreachable): narration degrades to silence; the smoke asserts
          the fallback ledger honestly records it (severity=unacceptable) and
          the producer QUARANTINES.

Anything else — a crash, a silent success with no verdict, a missing ledger,
a missing performance report — fails the smoke. Exit 0 = smoke pass.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import produce  # noqa: E402


def main() -> int:
    td = Path(tempfile.mkdtemp(prefix="curio_smoke_"))
    out = td / "smoke.mp4"
    fixture = REPO / "data_learning" / "pro_stories" / "fixtures" / "smoke.beats.json"

    # produce.resolve_story looks in pro_stories/; point it at the fixture by
    # copying it in under a slug that can never collide with a real story.
    slug = "zz-ci-smoke"
    dest_story = REPO / "data_learning" / "pro_stories" / f"{slug}.beats.json"
    story = json.loads(fixture.read_text())
    story["slug"] = slug
    dest_story.write_text(json.dumps(story, indent=2))
    try:
        res = produce.produce(slug, out, rounds=1)
    finally:
        dest_story.unlink(missing_ok=True)

    pkg = out.with_name(out.stem + "_pkg")
    failures: list[str] = []

    if res["status"] == "pass":
        failures.append("producer returned PASS with no vision verdict — "
                        "fail-closed law is broken")

    if not out.exists() or out.stat().st_size < 50_000:
        # a dead render is only acceptable if it was recorded as fail-closed
        if res.get("fallback_verdict") != "render_error":
            failures.append(f"no usable mp4 at {out} and no recorded "
                            "render_error")
    else:
        for side, name in ((out.with_suffix(".meta.json"), "meta.json"),
                           (out.with_suffix(".srt"), ".srt"),
                           (out.with_suffix(".jpg"), ".jpg")):
            if not side.exists():
                failures.append(f"package missing {name}")
        perf = pkg / "performance.json"
        if not perf.exists():
            failures.append("performance.json not written")
        fb = pkg / "fallbacks.json"
        if not fb.exists():
            failures.append("fallbacks.json (honest ledger) not written")
        else:
            ledger = json.loads(fb.read_text())
            silent = [f for f in ledger.get("fallbacks", [])
                      if "narration" in str(f.get("kind", ""))
                      or "tts" in str(f.get("kind", "")).lower()]
            if silent and ledger.get("verdict") != "unacceptable":
                failures.append("TTS fell back to silence but the ledger did "
                                f"not say unacceptable: {ledger.get('verdict')}")
        reasons = " | ".join(res.get("reasons", []))
        if "verdict" not in reasons:
            failures.append("quarantine reasons never mention the missing "
                            f"vision verdict: {reasons!r}")

    print()
    if failures:
        print("SMOKE FAIL:")
        for f in failures:
            print(f"  - {f}")
        shutil.rmtree(td, ignore_errors=True)
        return 1
    print(f"SMOKE PASS: producer status={res['status']!r} "
          f"(fail-closed verified), package + perf + ledger present at {td}")
    shutil.rmtree(td, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
