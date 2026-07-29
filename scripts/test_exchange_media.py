#!/usr/bin/env python3
"""Tests for the generated-media provider: deterministic auto ids, request
dedupe across renders, answered-ask fetching (download stubbed), provenance
stamping, the never-raise contract, and debt listing."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import exchange_media as xm  # noqa: E402

FID = "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuV"


def main():
    # 1. auto ids are deterministic and normalize whitespace/case
    a = xm.auto_id("Hands counting  cash")
    assert a == xm.auto_id("hands counting cash") == xm.auto_id(
        " HANDS   COUNTING CASH ")
    assert a.startswith("image-auto-") and a != xm.auto_id("something else")
    print("ok  1. same brief -> same id, across renders and whitespace")

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        xm.REQ, xm.RES = root / "req", root / "res"
        xm.CACHE = root / "cache"

        # 2. maybe_request files once, then dedupes
        rid = xm.maybe_request("empty wallet on a table", purpose="test")
        assert rid and (xm.REQ / f"{rid}.json").exists()
        before = (xm.REQ / f"{rid}.json").read_text()
        assert xm.maybe_request("empty  WALLET on a table") == rid
        assert (xm.REQ / f"{rid}.json").read_text() == before
        print("ok  2. auto-ask filed once; re-render dedupes, never clobbers")

        # 3. open_requests lists it as a debt; answering clears it
        debts = xm.open_requests()
        assert [x["id"] for x in debts] == [rid], debts
        (xm.RES / f"{rid}.json").parent.mkdir(parents=True, exist_ok=True)
        (xm.RES / f"{rid}.json").write_text(json.dumps(
            {"id": rid, "drive_file_id": FID, "by": "chatgpt",
             "filename": "wallet.png"}))
        assert xm.open_requests() == []
        print("ok  3. debt appears while open, clears when answered")

        # 4. maybe_fetch on the answered ask (download stubbed) returns a
        # provenance-stamped candidate; a cached file skips the download
        import exchange as ex
        calls = []

        def fake_fetch(a):
            calls.append(a.id)
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_bytes(b"\xff\xd8" + b"x" * 9000)
            return 0
        real = ex.cmd_fetch
        ex.cmd_fetch = fake_fetch
        try:
            got = xm.maybe_fetch(rid)
            assert got and Path(got["path"]).exists()
            assert got["source"] == "exchange"
            assert got["source_class"] == "generated"
            assert "AI-generated" in got["license"]
            assert "brief" in got["attribution"]
            again = xm.maybe_fetch(rid)
            assert again and calls == [rid]     # second hit came from cache
        finally:
            ex.cmd_fetch = real
        print("ok  4. answered ask fetches once, provenance stamped, cached")

        # 5. unanswered / failing asks return None, never raise
        assert xm.maybe_fetch("image-auto-0000000000") is None
        ex.cmd_fetch = lambda a: 1                       # not link-shared
        try:
            (xm.RES / "image-auto-bad.json").write_text(json.dumps(
                {"id": "image-auto-bad", "drive_file_id": FID}))
            (xm.REQ / "image-auto-bad.json").write_text(json.dumps(
                {"id": "image-auto-bad", "brief": "x"}))
            assert xm.maybe_fetch("image-auto-bad") is None
        finally:
            ex.cmd_fetch = real
        print("ok  5. no answer / failed download -> None, never a crash")

    # 6. the render path is actually wired (call-graph guard)
    pro = (REPO / "data_learning" / "pro_render.py").read_text()
    assert "exchange_asset" in pro and "maybe_request" in pro \
        and "exchange_media.maybe_fetch(exchange_media.auto_id" in pro
    plan = (REPO / "data_learning" / "planner.py").read_text()
    assert "exchange_asset" in plan
    wf = (REPO / ".github" / "workflows" / "curiosity.yml").read_text()
    assert "exchange/requests/*.json" in wf, \
        "CI does not persist auto-filed asks — they die with the runner"
    print("ok  6. renderer, planner, and CI persistence are wired")

    print("exchange media: 6/6 tests pass")


if __name__ == "__main__":
    main()
