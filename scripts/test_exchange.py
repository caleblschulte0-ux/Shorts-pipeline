#!/usr/bin/env python3
"""Tests for the exchange mailbox: link parsing (including the junk that must
be refused), the open/answered state rule, and refusal to clobber."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import exchange as ex  # noqa: E402

REAL = "1a2B3c4D5e6F7g8H9i0JkLmNoPqRsTuV"


def main():
    # 1. every Drive URL shape resolves to the same id
    for url in (f"https://drive.google.com/file/d/{REAL}/view?usp=sharing",
                f"https://drive.google.com/open?id={REAL}",
                f"https://drive.google.com/uc?export=download&id={REAL}",
                REAL):
        assert ex.drive_file_id(url) == REAL, url
    print("ok  1. share links, open links, download links and bare ids parse")

    # 2. junk is refused rather than silently stored — a response pointing at
    # nothing is worse than no response
    for junk in ("not-a-link", "", "   ", "https://example.com/cat.png",
                 "shortid123", "wallet.png"):
        assert ex.drive_file_id(junk) is None, junk
    print("ok  2. junk links refused (incl. the 'not-a-link' false positive)")

    # 3. open vs answered is decided purely by the response file existing
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ex.REQ, ex.RES = root / "requests", root / "responses"
        rid = "image-TEST"
        ex._write(ex.REQ / f"{rid}.json", {"id": rid, "brief": "a wallet"})
        assert not (ex.RES / f"{rid}.json").exists()

        class A:
            id = rid
            drive_url = f"https://drive.google.com/file/d/{REAL}/view"
            filename = "wallet.png"
            notes = ""
            sender = "chatgpt"
            push = False
        assert ex.cmd_respond(A()) == 0
        doc = json.loads((ex.RES / f"{rid}.json").read_text())
        assert doc["drive_file_id"] == REAL and doc["answered_at"]
        print("ok  3. responding records the resolved id and closes the ask")

        # 4. a response to an unknown request is refused
        class B(A):
            id = "image-NOPE"
        assert ex.cmd_respond(B()) == 2
        print("ok  4. cannot answer a request that does not exist")

        # 5. requests never silently overwrite
        class C:
            id = rid
            kind = "image"
            brief = "something else"
            purpose = ""
            aspect = "16:9"
            style = "photographic"
            sender = "github"
            recipient = "chatgpt"
            push = False
        assert ex.cmd_request(C()) == 2
        print("ok  5. an existing id is never clobbered")

    print("exchange: 5/5 tests pass")


if __name__ == "__main__":
    main()
