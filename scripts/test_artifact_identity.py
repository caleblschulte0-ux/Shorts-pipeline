#!/usr/bin/env python3
"""Negative-control tests for package identity (PR#173 adoption A).

Every tampering case from the reference's control list must be DETECTED:
replace the video after judgment; copy an old verdict onto a new render;
modify story or captions after the manifest; hand-edit the manifest itself.
Plus the positive path: an untouched package verifies clean and its bound
verdict passes evaluation.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import artifact_identity as ai  # noqa: E402
import judge_verdict as jv      # noqa: E402
import produce                  # noqa: E402

GOOD = {"personality": 4.0, "reject_labels": [],
        "card_fraction_estimate": 0.2, "one_line": "t"}


def build_package(td: Path) -> tuple[Path, Path]:
    out = td / "film.mp4"
    pkg = td / "film_pkg"
    pkg.mkdir()
    out.write_bytes(b"VIDEO-v1" * 4096)
    out.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n")
    out.with_suffix(".jpg").write_bytes(b"J")
    out.with_suffix(".meta.json").write_text("{}")
    (pkg / "fallbacks.json").write_text('{"verdict": "ok", "fallbacks": []}')
    story = td / "s.beats.json"
    story.write_text('{"slug": "s", "beats": []}')
    return out, story


def main():
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        out, story = build_package(td)
        m = ai.build_manifest(out, story_path=story, director_rc=0)
        ok, reasons = ai.verify_manifest(out, story_path=story)
        assert ok and not reasons, reasons
        assert m["director_rc"] == 0 and m["artifacts"]["video"]["sha256"]
        print("ok  1. untouched package verifies clean")

        jv.write(out, dict(GOOD))
        res = produce.evaluate(out, 0)
        assert res["status"] == "pass", res
        print("ok  2. hash-bound verdict on the same render -> PASS")

        # NEGATIVE: replace the video AFTER judgment (mtime is newer, so the
        # old mtime rule alone would... the hash rule must catch it regardless)
        out.write_bytes(b"VIDEO-v2-swapped" * 4096)
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine", res
        assert any("DIFFERENT render" in r for r in res["reasons"]), res["reasons"]
        ok, reasons = ai.verify_manifest(out, story_path=story)
        assert not ok and any("video" in r for r in reasons)
        print("ok  3. video replaced after judgment -> verdict refused + manifest flags it")

    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        out, story = build_package(td)
        ai.build_manifest(out, story_path=story, director_rc=0)
        # NEGATIVE: copy a verdict from ANOTHER render (bound to other hash)
        other = dict(GOOD)
        other_clean = jv.validate(other)
        other_clean["mp4_sha256"] = "0" * 64
        (td / "film_pkg" / "verdict.json").write_text(json.dumps(other_clean))
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("DIFFERENT render" in r for r in res["reasons"]), res["reasons"]
        print("ok  4. copied verdict from another render -> refused")

        # NEGATIVE: unbound verdict (no hash at all) fails closed
        unbound = jv.validate(dict(GOOD))
        (td / "film_pkg" / "verdict.json").write_text(json.dumps(unbound))
        res = produce.evaluate(out, 0)
        assert res["status"] == "quarantine"
        assert any("no mp4_sha256 binding" in r for r in res["reasons"]), res["reasons"]
        print("ok  5. unbound verdict -> fails closed")

        # NEGATIVE: story edited after render
        story.write_text('{"slug": "s", "beats": [{"changed": true}]}')
        ok, reasons = ai.verify_manifest(out, story_path=story)
        assert not ok and any("story" in r for r in reasons), reasons
        print("ok  6. story modified after render -> manifest flags it")

        # NEGATIVE: captions swapped
        out.with_suffix(".srt").write_text("tampered")
        ok, reasons = ai.verify_manifest(out, story_path=story)
        assert any("captions" in r for r in reasons), reasons
        print("ok  7. captions replaced -> manifest flags it")

        # NEGATIVE: hand-edited manifest
        mp = ai.manifest_path(out)
        doc = json.loads(mp.read_text())
        doc["artifacts"]["captions"]["sha256"] = ai.sha256_file(out.with_suffix(".srt"))
        doc["artifacts"]["story"]["sha256"] = "f" * 64
        mp.write_text(json.dumps(doc))
        ok, reasons = ai.verify_manifest(out, story_path=story)
        assert any("self-hash" in r for r in reasons), reasons
        print("ok  8. hand-edited manifest -> self-hash mismatch")

    print("artifact identity: 8/8 negative-control tests pass")


if __name__ == "__main__":
    main()
