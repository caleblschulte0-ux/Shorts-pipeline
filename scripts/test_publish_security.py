#!/usr/bin/env python3
"""Tests for the publish security scan: clean payloads pass, leaked secrets /
credential fields / internal-instruction fields block, warnings (emails,
URLs in sources) do NOT block, and a scanner crash fails closed."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import publish_security as ps  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "curiosity_test.mp4"

        # 1. clean payload passes and writes a report
        ok, reasons = ps.scan_upload(out, "Where Money Goes",
                                     "A film about rent and groceries.\n"
                                     "Sources: BLS CPI 2024.",
                                     ["money", "economics"])
        assert ok and not reasons, reasons
        rep = json.loads(out.with_suffix(".security.json").read_text())
        assert rep["valid"] is True
        print("ok  1. clean payload passes; report written")

        # 2. a leaked token in the description BLOCKS
        ok, reasons = ps.scan_upload(
            out, "t", "debug: Bearer abcdefghijklmnop1234 was used")
        assert not ok and "BLOCKING" in reasons[0], reasons
        rep = json.loads(out.with_suffix(".security.json").read_text())
        assert rep["valid"] is False and rep["blocking_paths"]
        print("ok  2. leaked bearer token blocks the upload")

        # 3. a credential-named field in meta BLOCKS
        out.with_suffix(".meta.json").write_text(json.dumps(
            {"chapters": [], "sources": [{"api_key": "whatever"}],
             "duration": 240}))
        ok, reasons = ps.scan_upload(out, "t", "fine text")
        assert not ok, reasons
        print("ok  3. credential-named field in public meta blocks")

        # 4. warnings (email in sources) do NOT block, but are recorded
        out.with_suffix(".meta.json").write_text(json.dumps(
            {"chapters": [], "duration": 240,
             "sources": ["contact: stats@bls.gov",
                         "https://www.bls.gov/cpi/"]}))
        ok, reasons = ps.scan_upload(out, "t", "fine text")
        assert ok, reasons
        rep = json.loads(out.with_suffix(".security.json").read_text())
        assert rep["warnings"] >= 1
        print("ok  4. warnings (emails/URLs) recorded but do not block")

        # 5. internal-instruction key blocks (planner reasoning must not ship)
        out.with_suffix(".meta.json").write_text(json.dumps(
            {"chapters": [], "duration": 240,
             "planner_reasoning": "internal: judge said beat 3 weak"}))
        ok, reasons = ps.scan_upload(out, "t", "fine")
        assert not ok, reasons
        print("ok  5. internal-instruction field blocks")

        # 6. scanner crash fails CLOSED
        out.with_suffix(".meta.json").unlink()
        real = ps.build_public_payload
        ps.build_public_payload = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom"))
        try:
            ok, reasons = ps.scan_upload(out, "t", "fine")
        finally:
            ps.build_public_payload = real
        assert not ok and "unscanned" in reasons[0], reasons
        print("ok  6. scanner failure refuses to publish (fail-closed)")

    print("publish security: 6/6 tests pass")


if __name__ == "__main__":
    main()
